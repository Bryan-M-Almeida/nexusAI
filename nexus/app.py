"""Desktop window (pywebview) and the API exposed to the interface."""
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta

import webview

from . import (MODEL_NAME, __version__, assistant, bridge, control, features, gpu_tune, i18n, knowledge, legal, llm, memory,
               memory_import, notify, profile, training,
               library, netprobe, performance, scheduler, skills, tools, workspace)
from . import files as filereader
from .logs import log, setup as setup_logs
from .config import WEB_DIR, settings
from .db import db
from .i18n import LANGS, detect, lang

SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+|\n+")
_window: webview.Window | None = None
_fullscreen = False
_pending: list[str] = []
_ui_ready = threading.Event()


def emit(event: str, payload=None):
    """Push an event to the interface (queued until the page is ready)."""
    script = f"window.nexus && window.nexus.on({json.dumps(event)}, {json.dumps(payload, ensure_ascii=False, default=str)})"
    if _window is None or not _ui_ready.is_set():
        _pending.append(script)
        return
    try:
        _window.evaluate_js(script)
    except Exception:
        pass


class Api:
    """Every public method is callable from JS as window.pywebview.api.<name>()."""

    def __init__(self):
        from .voice import Listener, Speaker

        self._brain = assistant.Assistant(self._on_brain_event, control_hook=self._speech_control,
                                          confirm_hook=self._confirm_command)
        tools.ui_hook = lambda nav: emit("ui_open", nav)  # the model's open_interface tool (v0.16.5)
        self._speaker = Speaker(lambda s: emit("voice", s), lambda payload: emit("speak_env", payload))
        self._listener = Listener(self._on_voice_text, lambda s: emit("voice", s), self._speaker,
                                  on_level=lambda level: emit("mic_level", level),
                                  on_progress=lambda pct: emit("stt_progress", pct))
        scheduler.start(self._on_alert)
        netprobe.start(lambda st: emit("network", {"effective": netprobe.effective(), "quality": st}))
        bridge.start(settings["bridge_port"], self._on_profile)
        self._tts_buf, self._tts_streamed, self._reply_lang = "", False, None
        self.ai_state = "cold"  # cold | warming | ready | offline
        self._hidden_since = None  # v0.14: when the window was minimized (None = visible)
        self._podcast = None  # v0.15: {"id", "pos", "title"} while a book is being read aloud
        self._attachments: list[dict] = []  # v0.15: files attached to the next message
        library.player = self.podcast_start
        threading.Thread(target=self._background_watch, daemon=True, name="background").start()

    def _confirm_command(self, command: str) -> bool:
        """The AI wants to run a command in the workspace: ask the user (dialog + voice) and wait up to 3 min."""
        import uuid

        cid = uuid.uuid4().hex[:10]
        item = workspace.request_confirmation(cid)
        emit("confirm", {"id": cid, "command": command, "workspace": workspace.active["name"] if workspace.active else ""})
        self._speaker.say(i18n.t("confirm_command"), remember=False, force=settings["voice_enabled"])
        answered = item["event"].wait(180)
        emit("confirm_done", {"id": cid, "ok": answered and item["ok"]})
        return bool(answered and item["ok"])

    def confirm_command(self, cid, ok):
        workspace.answer_confirmation(cid, bool(ok))

    def _on_alert(self, alert):
        """Scheduler reminders and the daily briefing: notification center + in-app toast, and - outside quiet
        hours - a Windows notification and the voice (even in text mode; muting the AI voice silences it)."""
        title = {"event": i18n.t("notif_event"), "task": i18n.t("notif_task")}.get(alert["kind"], alert.get("title", "NEXUS"))
        quiet = notify.in_quiet_hours() or self.focus()  # focus mode: only the bell, no voice/pop-up
        item = notify.add(alert["kind"], title, alert["text"])
        emit("alert", {**alert, "notification": item, "quiet": quiet, "sound": settings["notify_sound"] and not quiet})
        if quiet:
            return
        if settings["desktop_notifications"]:
            notify.toast(f"N.E.X.U.S · {title}", alert["text"])
        if settings["speak_reminders"] and settings["voice_enabled"]:
            self._speaker.say(alert["text"], force=True, remember=False)

    def _on_brain_event(self, event, payload):
        """Forward to the UI and speak while the answer is still being generated (sentence by sentence)."""
        emit(event, payload)
        if event == "done" and workspace.active:
            emit("workspace", self.workspace_view())
        if event == "token":
            if not self._brain.cancel.is_set():
                self._tts_buf += payload
                self._speak_ready_sentences()
        elif event == "reset":  # text before a tool call is narration, not the answer
            self._tts_buf = ""
        elif event == "done":
            if payload.get("speak"):
                if self._tts_streamed:
                    self._speak_ready_sentences(final=True)
                else:  # e.g. the emergency protocol: no tokens were streamed
                    self._speaker.say(payload["text"], lang_code=self._reply_lang)
                self._speaker.last_text = payload["text"]
            self._tts_buf, self._tts_streamed = "", False

    def _speak_ready_sentences(self, final=False):
        """Queue complete sentences (>= 30 chars, so "1." of a list is not spoken alone) as soon as they exist."""
        buf = self._tts_buf
        if final:
            chunk, rest = buf, ""
        else:
            cut = 0
            for m in SENTENCE_END.finditer(buf):
                if m.start() - cut >= 30:
                    cut = m.end()
            chunk, rest = buf[:cut], buf[cut:]
        if chunk.strip():
            self._speaker.say(chunk, remember=False, lang_code=self._reply_lang)
            self._tts_streamed = True
        self._tts_buf = rest

    # -- lifecycle -----------------------------------------------------------
    def ui_ready(self):
        _ui_ready.set()
        while _pending:
            _window.evaluate_js(_pending.pop(0))

    def boot(self):
        """Run boot checks; the interface shows each step during the intro animation."""
        steps = []

        def step(key, ok, detail=""):
            steps.append({"key": key, "ok": ok, "detail": detail})
            emit("boot", steps[-1])

        step("memory", True, f"{len(memory.all_memories())}")
        seeded = knowledge.load_seed()
        learned = knowledge.scan_inbox()
        kb = knowledge.stats()
        step("knowledge", bool(kb), f"{sum(k['chunks'] for k in kb)}" + (f" +{len(learned)}" if learned or seeded else ""))
        st = llm.status()
        step("ai", st["online"] and st.get("model_ready", False), st["model"])
        if st["online"] and st.get("model_ready"):
            threading.Thread(target=self._warm_up, daemon=True, name="warm-up").start()
        else:
            self.ai_state = "offline"
        step("voice", self._listener.model_state != "error", f"{settings['stt_model']} · {self._listener.model_state}")
        self._sync_listening()
        return {"profile": db.get_profile(), "lang": lang(), "llm": st, "settings": dict(settings),
                "stt": self._listener.model_state, "version": __version__, "model_name": MODEL_NAME,
                "fullscreen": _fullscreen, "terms": legal.state()}

    # -- Terms of Use / Privacy Policy (v0.17.0) -----------------------------------------------------------------
    def accept_terms(self):
        st = legal.accept()
        self._sync_listening()  # the microphone only opens after consent
        threading.Thread(target=netprobe.refresh, daemon=True, name="netprobe").start()
        return st

    def revoke_terms(self):
        st = legal.revoke()
        self._listener.set_live(False)
        return st

    @staticmethod
    def terms_state():
        return legal.state()

    # -- Settings > Performance > Ollama on AMD + Vulkan (v0.17.0) -------------------------------------------------
    @staticmethod
    def gpu_tune_status():
        return gpu_tune.status()

    def gpu_tune(self, on):
        result = gpu_tune.apply(bool(on))
        if result.get("restarted"):
            threading.Thread(target=self._warm_up, daemon=True, name="warm-up").start()
        return result

    def _warm_up(self):
        """Load the model and cache the fixed prompt while the boot animation plays (v0.6: 1st reply 30 s -> ~1 s)."""
        self.ai_state = "warming"
        emit("ai_state", {"state": "warming"})
        t0 = time.time()
        try:
            assistant.warm_up()
            self.ai_state = "ready"
        except Exception as exc:
            self.ai_state = "offline"
            emit("ai_state", {"state": "offline", "error": str(exc)})
            return
        emit("ai_state", {"state": "ready", "seconds": round(time.time() - t0, 1)})

    def greet(self):
        text = assistant.greeting()
        if settings["greet_on_start"]:
            self._speaker.say(text)
        return text

    # -- modes and dock buttons ------------------------------------------------
    def _sync_listening(self):
        """Audio mode with the mic unmuted = continuous conversation; otherwise the mic is closed.
        v0.17.0: never before the Terms of Use / Privacy Policy are accepted."""
        self._listener.set_live(legal.accepted() and settings["ui_mode"] == "audio" and not settings["mic_muted"])

    def set_mode(self, mode):
        settings.apply({"ui_mode": "text" if mode == "text" else "audio"})
        if settings["ui_mode"] == "text":
            self._speaker.stop()
        self._sync_listening()
        return self.state()

    def set_mic(self, muted):
        settings.apply({"mic_muted": bool(muted)})
        if not muted:
            self._listener.ensure_model()  # first use downloads the Whisper model
        self._sync_listening()
        return self.state()

    def set_ai_voice(self, enabled):
        settings.apply({"voice_enabled": bool(enabled)})
        if not enabled:
            self._speaker.stop()
        return self.state()

    def set_ai_mode(self, mode):
        """Left rail: "assistant" (complete) or "direct" (shortest exact answer)."""
        settings.apply({"ai_mode": mode if mode in assistant.MODES else "assistant"})
        spoken = i18n.t("mode_on", mode=i18n.t("mode_" + settings["ai_mode"]))
        self._speaker.stop()
        self._speaker.say(spoken, remember=False)
        return {**self.state(), "spoken": spoken}

    def set_temporary(self, on):
        """Right rail: temporary conversation - kept only in RAM, never saved, nothing learned automatically."""
        self._speaker.stop()
        memory.set_temporary(bool(on))
        return self.state()

    def state(self):
        return {"ui_mode": settings["ui_mode"], "mic_muted": settings["mic_muted"],
                "voice_enabled": settings["voice_enabled"], "stt": self._listener.model_state,
                "stt_error": self._listener.model_error, "ai_mode": settings["ai_mode"],
                "temporary": memory.temporary, "can_repeat": bool(assistant.last_reply()),
                "conversation": memory.current_conversation(), "focus": self.focus(),
                "workspace": workspace.active, "network": settings["network_mode"],
                "network_effective": netprobe.effective(), "net_quality": netprobe.state,
                "performance": settings["performance"], "ai_target": settings["ai_target"]}

    def interrupt(self):
        """Dock "interrupt" / Esc: stop speaking and cancel the answer being generated."""
        self._speaker.stop()
        self._brain.interrupt()
        emit("control", {"action": "stop"})

    def repeat(self):
        """Dock "repeat": "I don't think you understood, I'll repeat." + the same last answer."""
        text = assistant.last_reply()
        if not text:
            return {"intro": i18n.t("nothing_to_repeat"), "text": ""}
        self._speaker.stop()
        self._speaker.say(i18n.t("repeat_button"), remember=False)
        self._speaker.say(text)
        return {"intro": i18n.t("repeat_button"), "text": text}

    # -- conversation ----------------------------------------------------------
    def _speech_control(self, action):
        """pause / resume / stop on the voice (also used by the model's conversation_control tool)."""
        if action == "pause":
            self._speaker.pause()
        elif action == "resume":
            self._speaker.resume()
        elif action == "stop":
            self._speaker.stop()
            self._brain.interrupt()
        emit("control", {"action": action})

    def _handle_control(self, action, said=""):
        """Short commands recognised locally: act instantly, no model round trip."""
        if action in ("pause", "resume", "stop"):
            self._speech_control(action)
            return
        previous = assistant.last_reply()
        if not previous:
            emit("control", {"action": action, "intro": i18n.t("nothing_to_repeat"), "text": ""})
            self._speaker.say(i18n.t("nothing_to_repeat"), remember=False)
            return
        self._speaker.stop()
        if action == "repeat":
            emit("control", {"action": "repeat", "intro": i18n.t("repeat_intro"), "text": previous})
            self._speaker.say(i18n.t("repeat_intro"), remember=False)
            self._speaker.say(previous)
        else:  # clearer: say so right away, then let the model rephrase
            emit("control", {"action": "clearer", "intro": i18n.t("clearer_intro")})
            self._speaker.say(i18n.t("clearer_intro"), remember=False)
            request = i18n.t("clearer_request", said=said.strip() or "?")
            threading.Thread(target=self._brain.ask, args=(request,), daemon=True).start()

    def send(self, text, spoken=False):
        action = control.detect(text)
        if action:
            self._handle_control(action, text)
            return {"control": action}
        self._reply_lang = detect(text) or lang()
        attachments, self._attachments = self._attachments, []
        threading.Thread(target=self._brain.ask, args=(text, spoken, attachments), daemon=True).start()
        return {"control": None}

    def history(self):
        return memory.history(settings["history_turns"])

    def clear_history(self):
        memory.clear_history()

    # -- library and podcast (v0.15) ---------------------------------------------------------------------------
    def books(self):
        return library.listing()

    def add_books(self, paths=None):
        """Settings-free import: file dialog (or paths dropped on the window)."""
        if not paths:
            paths = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                                               file_types=("Books (*.pdf;*.epub;*.docx;*.txt;*.md)",)) or []
        results = []
        for path in paths:
            try:
                results.append({"ok": True, **library.add(path)})
            except filereader.FileError as exc:
                results.append({"ok": False, "file": str(path), "error": str(exc)})
        return {"results": results, "books": library.listing()}

    def delete_book(self, bid):
        if self._podcast and self._podcast["id"] == int(bid):
            self.podcast_stop()
        library.delete(int(bid))
        return library.listing()

    def book_page(self, bid, position=None):
        book = library.get(int(bid))
        if not book:
            return {"error": "not found"}
        return {**library.page(book["id"], book["position"] if position is None else int(position)), "book": book}

    def podcast_start(self, bid, position=None):
        """Read a book aloud from a position, part by part; each finished part saves the position."""
        book = library.get(int(bid))
        if not book:
            return {"error": "not found"}
        self._speaker.stop()
        pos = book["position"] if position is None else int(position)
        self._podcast = {"id": book["id"], "pos": pos, "title": book["title"], "lang": book["language"] or None}
        self._podcast_next()
        return self.podcast_state()

    def _podcast_next(self):
        pod = self._podcast
        if not pod:
            return
        part, end = library.next_part(pod["id"], pod["pos"])
        if not part:
            emit("podcast", {**self.podcast_state(), "finished": True})
            self._podcast = None
            return

        def done():
            if self._podcast is pod:
                pod["pos"] = end
                library.set_position(pod["id"], end)
                emit("podcast", self.podcast_state())
                self._podcast_next()

        self._speaker.say(part, force=True, remember=False, lang_code=pod["lang"], on_done=done)
        emit("podcast", {**self.podcast_state(), "reading": part[:200]})

    def podcast_state(self):
        pod = self._podcast
        if not pod:
            return {"active": False}
        book = library.get(pod["id"]) or {"chars": 1}
        return {"active": True, "id": pod["id"], "title": pod["title"], "position": pod["pos"],
                "progress": round(pod["pos"] / max(book["chars"], 1), 4), "paused": self._speaker.paused.is_set()}

    def podcast_stop(self):
        self._podcast = None
        self._speaker.stop()
        emit("podcast", {"active": False})
        return {"active": False}

    def podcast_toggle(self):
        if self._speaker.paused.is_set():
            self._speaker.resume()
        else:
            self._speaker.pause()
        return self.podcast_state()

    # -- attachments (v0.15) -----------------------------------------------------------------------------------------
    def attach_files(self, paths=None):
        if not paths:
            paths = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True) or []
        out = []
        for path in paths:
            try:
                data = filereader.read(path)
                item = {"name": data["name"], "kind": data["kind"], "text": data["text"], "chars": len(data["text"])}
                self._attachments.append(item)
                out.append({"ok": True, "name": item["name"], "kind": item["kind"], "chars": item["chars"]})
            except filereader.FileError as exc:
                out.append({"ok": False, "name": pathlib_name(path), "error": str(exc)})
        return {"results": out, "pending": [{"name": a["name"], "kind": a["kind"]} for a in self._attachments]}

    def attach_blob(self, name, b64):
        """Drag & drop without a file path (the WebView gives only the bytes): saved to a temp file and read."""
        import base64

        from .config import DATA_DIR

        tmp = DATA_DIR / "tmp"
        tmp.mkdir(exist_ok=True)
        path = pathlib_safe(tmp, name)
        path.write_bytes(base64.b64decode(b64.split(",", 1)[-1]))
        try:
            return self.attach_files([str(path)])
        finally:
            path.unlink(missing_ok=True)

    def clear_attachments(self):
        self._attachments = []
        return {"pending": []}

    # -- background / suspended (v0.14) ----------------------------------------------------------------------------
    def set_background(self, state):
        """The interface reports "visible" | "blurred" (not in focus) | "hidden" (minimized)."""
        self._listener.set_background(state != "visible")
        if state == "hidden":
            self._hidden_since = self._hidden_since or time.time()
        else:
            self._hidden_since = None
            if self._listener.released:  # back on screen: reload the voice model quietly (~1 s, from disk)
                self._listener.released = False
                threading.Thread(target=self._listener._load_model, daemon=True, name="stt-load").start()
        return {"wake_only": self._listener.wake_required()}

    def _background_watch(self):
        """Minimized for a while with the microphone off: free Whisper's memory (reloaded when needed)."""
        while True:
            time.sleep(30)
            hidden = self._hidden_since and time.time() - self._hidden_since >= settings["bg_release_minutes"] * 60
            if hidden and self._listener.model is not None and self._listener.mode == "off":
                self._listener.release()
                log.info("minimized: voice model released from memory")

    # -- one-click local AI <-> API (v0.14) -------------------------------------------------------------------------
    def switch_ai(self, target):
        need_setup = llm.switch_target(target)
        st = llm.status() if not need_setup else {"online": False, "model": settings["llm_model"], "models": []}
        return {**self.state(), "need_setup": need_setup, "llm": st, "settings": dict(settings)}

    # -- connection modes and performance profiles (v0.12) --------------------------------------------------------
    def performance_info(self):
        return performance.check()

    def set_network(self, mode):
        settings.apply({"network_mode": mode if mode in ("offline", "hybrid", "online") else "hybrid"})
        return {**self.state(), "llm": llm.status()}

    def set_performance(self, profile):
        """Apply a profile's settings at once (Settings > Performance). Returns the new settings."""
        old_stt = settings["stt_model"]
        settings.apply(performance.settings_for(profile if profile in performance.PROFILES else "balanced"))
        if settings["stt_model"] != old_stt:
            self._listener.reload_model() if netprobe.effective() != "offline" else None
        return {**self.get_settings(), "state": self.state(), "perf": performance.check()}

    # -- focus mode and workspace (v0.11) -------------------------------------------------------------------------
    @staticmethod
    def focus() -> bool:
        """Focus mode: chosen by the user, or automatic while a workspace is open (Settings)."""
        return bool(settings["focus_mode"] or (workspace.active and settings["focus_in_workspace"]))

    def set_focus(self, on):
        settings.apply({"focus_mode": bool(on)})
        return self.state()

    def workspaces(self):
        return workspace.listing()

    def create_workspace(self, name, description=""):
        ws = workspace.create(name, description)
        return self.open_workspace(ws["id"])

    def open_workspace(self, wid):
        if not features.enabled("workspace"):
            return {"error": "beta_off"}
        self._speaker.stop()
        if memory.temporary:
            memory.set_temporary(False)
        ws = workspace.open_(int(wid))
        memory.enter_workspace(ws["id"], ws["conversation_id"])
        workspace.active = workspace.get(ws["id"])
        return {**self.state(), "messages": memory.conversation_messages(memory.current_conversation()),
                **self.workspace_view()}

    def close_workspace(self):
        self._speaker.stop()
        workspace.close()
        memory.leave_workspace()
        return {**self.state(), "messages": memory.history(settings["history_turns"])}

    def delete_workspace(self, wid):
        if workspace.active and workspace.active["id"] == int(wid):
            self.close_workspace()
        workspace.delete(int(wid))
        return workspace.listing()

    def workspace_view(self):
        """Files (with sizes) and the change journal for the side panel."""
        if not workspace.active:
            return {"files": [], "changes": []}
        root = workspace.root()
        files = [{"path": workspace.rel(p), "dir": p.is_dir(), "size": 0 if p.is_dir() else p.stat().st_size}
                 for p in list(workspace._walk(root))[:500]]
        return {"files": files, "changes": workspace.changes(40), "folder": str(root)}

    def read_workspace_file(self, path):
        try:
            return workspace.read_file(path)
        except workspace.WorkspaceError as exc:
            return {"error": str(exc)}

    def undo_workspace(self, change_id=None):
        result = workspace.undo(int(change_id) if change_id else None)
        return {**result, **self.workspace_view()}

    def open_workspace_folder(self):
        if workspace.active:
            try:
                os.startfile(workspace.root())
            except Exception:
                pass

    # -- conversations (v0.9) ----------------------------------------------------
    def conversations(self):
        return {"list": memory.conversations(), "current": memory.current_conversation()}

    def timeline(self, before_id=None):
        return memory.timeline(200, before_id)

    def new_conversation(self):
        """Right rail "New conversation": the next message starts a fresh one."""
        self._speaker.stop()
        if memory.temporary:
            memory.set_temporary(False)
        memory.new_conversation()
        return self.state()

    def open_conversation(self, conversation_id):
        self._speaker.stop()
        if memory.temporary:
            memory.set_temporary(False)
        ok = memory.open_conversation(int(conversation_id))
        return {"ok": ok, "messages": memory.conversation_messages(int(conversation_id)) if ok else [], **self.state()}

    def delete_conversation(self, conversation_id):
        memory.delete_conversation(int(conversation_id))
        return self.conversations()

    def rename_conversation(self, conversation_id, title):
        row = db.one("SELECT description FROM conversations WHERE id = ?", (int(conversation_id),))
        if row and title.strip():
            memory.set_conversation_title(int(conversation_id), title, row["description"], final=True)
        return self.conversations()

    def stop_speaking(self):
        self._speaker.stop()

    def list_voices(self):
        return {"voices": self._speaker.list_voices(), "error": self._speaker.error}

    def test_voice(self, text):
        """Speak a sample with the current voice settings, even if the AI voice is muted."""
        self._speaker.stop()
        self._speaker.say(text, force=True, remember=False)

    # -- training mode and memory import (v0.17.5, beta) -------------------------------------------------------
    @staticmethod
    def training_state():
        return training.state()

    def training_start(self, topic=""):
        """Rail button: same as saying "começa o treinamento"."""
        threading.Thread(target=self._brain._training_command, args=(("start", str(topic or "")),), daemon=True).start()

    def training_finish(self):
        threading.Thread(target=self._brain._training_command, args=(("finish", ""),), daemon=True).start()

    @staticmethod
    def training_history():
        return training.history()

    @staticmethod
    def training_delete(tid):
        training.delete(int(tid))
        return training.history()

    @staticmethod
    def import_prompt(lang_code=None):
        return {"prompt": memory_import.prompt(lang_code or lang()), "sources": memory_import.SOURCES}

    @staticmethod
    def import_memories(source, text):
        result = memory_import.import_text(str(source), str(text))
        emit("refresh")
        return result

    @staticmethod
    def memory_sources():
        return memory_import.by_source()

    def hold_start(self):
        """Beta (v0.16.8): talk while the key is held."""
        if not legal.accepted():
            return {"ok": False, "error": "terms"}
        if not self._listener.ensure_model():
            return {"ok": False, "error": self._listener.model_error or "loading"}
        self._listener.hold_start()
        return {"ok": True}

    def hold_stop(self):
        self._listener.hold_stop()

    @staticmethod
    def concept_map():
        """Concept map (beta, v0.16.8): skills and knowledge areas around the ring."""
        cats: dict = {}
        for d in knowledge.documents():
            cats.setdefault(d.get("category") or "Geral", []).append(d["title"])
        mems = [m["content"] for m in memory.all_memories()][:8]
        return {"skills": skills.summary()["skills"],
                "knowledge": [{"name": k, "items": v} for k, v in sorted(cats.items())],
                "memories": mems}

    def optimize(self, kind):
        """Settings > Performance > Optimize (v0.16.8): free RAM, clear caches, temporary files or conversations."""
        import gc

        from . import backup
        from .config import LOG_DIR

        before = _rss_mb()
        freed_disk = 0
        if kind in ("ram", "cache"):
            knowledge._cache.clear()
            tools._online_cache.clear()
            self._speaker.__dict__.get("_cache", {}).clear()
            if kind == "ram" and self._listener.mode == "off":
                self._listener.release()  # Whisper (~0.5 GB) reloads by itself when voice is used again
            gc.collect()
            if kind == "cache":
                size0 = db_path_size()
                db.execute("VACUUM")
                freed_disk = max(0, size0 - db_path_size())
            _trim_working_set()
        elif kind == "temp":
            import time as _t

            old = _t.time() - 30 * 86400
            for f in list(LOG_DIR.glob("nexus.log.*")) + [f for f in tools.REPORTS_DIR.glob("*.md") if f.stat().st_mtime < old]:
                try:
                    freed_disk += f.stat().st_size
                    f.unlink()
                except OSError:
                    pass
        elif kind == "data":
            saved = backup.create()  # always a backup first: this can't be undone otherwise
            for table in ("messages", "conversations", "notifications", "actions"):
                try:
                    db.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
            memory.new_conversation()
            emit("refresh")
            return {"ok": True, "backup": str(saved), "rss_mb": _rss_mb()}
        else:
            return {"ok": False, "error": "unknown"}
        return {"ok": True, "freed_mb": round(max(0, before - _rss_mb()), 1), "rss_mb": _rss_mb(),
                "freed_disk_mb": round(freed_disk / 1e6, 1)}

    def push_to_talk(self):
        if not legal.accepted():
            return {"ok": False, "error": "terms"}
        if not self._listener.ensure_model():  # first use downloads the Whisper model
            return {"ok": False, "error": self._listener.model_error or "loading"}
        self._listener.push_to_talk()
        return {"ok": True}

    def _on_voice_text(self, text, during_speech=False):
        action = control.detect(text)
        if action:
            emit("heard", {"text": text, "control": action})
            self._handle_control(action, text)
        elif not during_speech:  # while NEXUS talks only control commands count (echo protection)
            emit("heard", {"text": text})
            self._reply_lang = detect(text) or lang()
            threading.Thread(target=self._brain.ask, args=(text, True), daemon=True).start()

    def report_issue(self):
        """Settings button: save this conversation to a report file and show it in Explorer."""
        result = tools.report_issue("Relatório gerado pelo botão das Configurações")
        try:
            os.startfile(os.path.dirname(result["file"]))
        except Exception:
            pass
        return result

    # -- window ----------------------------------------------------------------
    def toggle_fullscreen(self):
        """Returns the new state: the interface hides the window buttons in full screen (v0.16.1)."""
        global _fullscreen
        _window.toggle_fullscreen()
        _fullscreen = not _fullscreen
        return _fullscreen

    @staticmethod
    def llm_status():
        """Light AI check for the ring's "AI unavailable" state (polled only while it is down)."""
        return llm.status()

    def speak_help(self, text):
        """"How to fix" on the ring: NEXUS says the steps out loud, even with the AI down."""
        self._speaker.stop()
        self._speaker.say(text, force=True, remember=False)

    def minimize(self):
        _window.minimize()

    def quit(self):
        _window.destroy()

    # -- profile ---------------------------------------------------------------
    def _on_profile(self, prof):
        emit("profile", {"profile": prof, "lang": lang()})
        emit("refresh")

    def quick_profile(self, name, profession="", language=""):
        """Onboarding without the landing page JSON: name (+ optional profession and language)."""
        data = {"name": str(name).strip(), "profession": str(profession).strip(),
                "language": language or {"pt": "pt-BR", "en": "en", "es": "es"}.get(lang(), "pt-BR")}
        return self.import_profile_text(json.dumps(data, ensure_ascii=False))

    # -- skills, backups, logs (v0.13) ------------------------------------------------------------------------
    def skills(self):
        return skills.summary()

    def create_backup(self):
        from . import backup

        try:
            path = backup.create()
        except Exception as exc:
            log.exception("manual backup failed")
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "file": str(path), "backups": backup.listing()}

    def list_backups(self):
        from . import backup

        return backup.listing()

    def restore_backup(self):
        """Pick a backup .zip; it is applied the next time NEXUS opens (current data is kept aside)."""
        from . import backup
        from .config import BACKUP_DIR

        paths = _window.create_file_dialog(webview.OPEN_DIALOG, directory=str(BACKUP_DIR),
                                           file_types=("NEXUS backup (*.zip)",))
        if not paths:
            return {"ok": False}
        result = backup.schedule_restore(paths[0])
        log.info(f"restore scheduled from {paths[0]}: {result}")
        return result

    def open_backups_folder(self):
        from .config import BACKUP_DIR

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(BACKUP_DIR)
        except Exception:
            pass

    def import_profile_text(self, text):
        try:
            prof = profile.import_profile(text)
        except (ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}
        self._on_profile(prof)
        return {"ok": True, "profile": prof}

    def import_profile_file(self):
        paths = _window.create_file_dialog(webview.OPEN_DIALOG, file_types=("JSON (*.json)",))
        if not paths:
            return {"ok": False}
        with open(paths[0], encoding="utf-8") as f:
            return self.import_profile_text(f.read())

    # -- knowledge -------------------------------------------------------------
    def import_knowledge_files(self):
        paths = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                                           file_types=("Docs (*.md;*.txt;*.pdf)",))
        results = []
        for p in paths or []:
            try:
                results.append({"ok": True, **knowledge.import_file(p)})
            except Exception as exc:
                results.append({"ok": False, "file": p, "error": str(exc)})
        emit("refresh")
        return results

    def learn(self, title, content, category):
        result = knowledge.learn(title, content, category or "aprendido")
        emit("refresh")
        return result

    def delete_document(self, doc_id):
        knowledge.delete_document(int(doc_id))

    def search_knowledge(self, query):
        return knowledge.search(query, limit=8)

    # -- dashboard -------------------------------------------------------------
    def dashboard(self):
        start = datetime.now().replace(hour=0, minute=0)
        return {
            "profile": db.get_profile(),
            "tasks": tools.list_tasks("pending"),
            "events": tools.list_events(start.isoformat(timespec="minutes"),
                                        (start + timedelta(days=14)).isoformat(timespec="minutes")),
            "memories": memory.all_memories(),
            "actions": memory.recent_actions(40),
            "knowledge": knowledge.stats(),
            "documents": knowledge.documents(),
            "collections": tools.list_collections(),
            "notes": tools.search_notes(""),
        }

    def collection(self, name):
        return tools.query_data(name, 100)

    def add_task(self, title, due=None):
        return tools.add_task(title, due or None)

    def complete_task(self, task_id):
        return tools.complete_task(int(task_id))

    def delete_task(self, task_id):
        return tools.delete_task(int(task_id))

    def delete_event(self, event_id):
        return tools.delete_event(int(event_id))

    def forget(self, memory_id):
        return memory.forget(int(memory_id))

    # -- settings --------------------------------------------------------------
    def get_settings(self):
        return {"settings": dict(settings), "llm": llm.status(), "langs": LANGS, "lang": lang(), "features": features.state(),
                "voices": self._speaker.voices, "presets": llm.PRESETS, "mics": self.list_mics()}

    # -- notifications (v0.10) -------------------------------------------------------------------------------
    def notifications(self):
        return notify.listing()

    def mark_notifications_read(self):
        notify.mark_read()

    def clear_notifications(self):
        notify.clear()

    def briefing_now(self):
        """Settings > Notifications > "Hear today's briefing now"."""
        self._on_alert({"kind": "briefing", "title": i18n.t("briefing_title"), "text": scheduler.briefing_text()})

    def test_notification(self):
        self._on_alert({"kind": "test", "title": "NEXUS", "text": i18n.t("notif_test")})

    # -- AI provider / microphone / data (v0.10) ---------------------------------------------------------------
    def test_llm(self, changes):
        """Save the AI provider fields and report whether the server answers and has the model."""
        settings.apply({k: v for k, v in changes.items() if k.startswith("llm_")})
        return llm.status()

    @staticmethod
    def list_mics():
        try:
            import sounddevice as sd

            default = sd.query_devices(kind="input")["name"]
            names = []
            for d in sd.query_devices():
                virtual = any(w in d["name"].lower() for w in ("mapeador", "mapper", "asignador"))  # sound mapper
                if d["max_input_channels"] > 0 and d["hostapi"] == 0 and not virtual and d["name"] not in names:
                    names.append(d["name"])
            return {"devices": names, "default": default}
        except Exception as exc:
            return {"devices": [], "default": "", "error": str(exc)}

    def open_data_folder(self):
        from .config import DATA_DIR

        try:
            os.startfile(DATA_DIR)
        except Exception:
            pass

    def save_settings(self, changes):
        restart_stt = changes.get("stt_model", settings["stt_model"]) != settings["stt_model"]
        new_mic = changes.get("mic_device", settings["mic_device"]) != settings["mic_device"]
        new_calendar = changes.get("calendar_ics_url", settings["calendar_ics_url"]) != settings["calendar_ics_url"]
        settings.apply(changes)
        if new_calendar and settings["calendar_ics_url"].strip():
            threading.Thread(target=lambda: (tools.sync_calendar(), emit("refresh")), daemon=True).start()
        if restart_stt:
            self._listener.reload_model()
        if new_mic:
            self._listener.reopen()
        return self.get_settings()


def _rss_mb() -> float:
    """This process's working set (RAM in use), in MB - Windows API, no extra package."""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k = _kernel32()
        k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return round(pmc.WorkingSetSize / 1e6, 1)
    except Exception:
        return 0.0


def _trim_working_set():
    """Give unused pages back to Windows (they come back on demand)."""
    try:
        k = _kernel32()
        k.K32EmptyWorkingSet(k.GetCurrentProcess())
    except Exception:
        pass


def _kernel32():
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = wintypes.HANDLE  # a 64-bit pseudo handle: the default int return type breaks it
    k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    k.K32EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    return k


def db_path_size() -> int:
    from .config import DATA_DIR

    f = DATA_DIR / "nexus.db"
    return f.stat().st_size if f.exists() else 0


def pathlib_name(path) -> str:
    from pathlib import Path

    return Path(str(path)).name


def pathlib_safe(folder, name: str):
    import re as _re

    return folder / (_re.sub(r"[^\w.\- ]+", "_", str(name))[:120] or "file")


def selftest() -> dict:
    """Headless release check (NEXUS.exe --selftest): writes selftest.json in the data folder."""
    from . import __version__, tts
    from .config import DATA_DIR

    report = {"version": __version__}
    try:
        engine = tts.Engine()
        voice, pitch = engine.pick(lang(), settings["voice_gender"])
        audio = tts.apply_effect(engine.render("NEXUS online.", voice, pitch), settings["voice_effect"])
        report["tts"] = {"ok": len(audio) > 0, "voices": [v.as_dict() for v in engine.voices],
                         "seconds": round(len(audio) / tts.RATE, 2)}
    except Exception as exc:
        report["tts"] = {"ok": False, "error": repr(exc)}
    try:
        knowledge.load_seed()
        report["knowledge_docs"] = len(knowledge.documents())
    except Exception as exc:
        report["knowledge_docs"] = repr(exc)
    report["llm"] = llm.status()
    try:
        import faster_whisper  # noqa: F401
        import sounddevice as sd

        from .voice import SpeechDetector

        report["stt"] = {"ok": True, "input_device": sd.query_devices(kind="input")["name"],
                         "vad": "silero" if SpeechDetector().session is not None else "energy (fallback)"}
    except Exception as exc:
        report["stt"] = {"ok": False, "error": repr(exc)}
    (DATA_DIR / "selftest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    return report


def _single_instance() -> bool:
    """Only one NEXUS at a time: two copies would fight over the microphone, the database and the AI (v0.13).
    The named mutex disappears by itself when the process ends, even after a crash."""
    if sys.platform != "win32":
        return True
    import ctypes

    global _mutex
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex = kernel32.CreateMutexW(None, False, "Local\\NEXUS-Assistant-single-instance")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(None, i18n.t("already_running"), "N.E.X.U.S", 0x40)
        return False
    return True


_mutex = None


def main():
    global _window, _fullscreen
    setup_logs()
    if "--selftest" in sys.argv:
        selftest()
        return
    if not _single_instance():
        return
    log.info(f"NEXUS {__version__} starting")
    threading.Thread(target=_daily_backup, daemon=True, name="backup").start()
    api = Api()
    _fullscreen = bool(settings["start_fullscreen"] and not os.environ.get("NEXUS_WINDOWED"))
    _window = webview.create_window(
        "N.E.X.U.S", str(WEB_DIR / "index.html"), js_api=api,
        width=1360, height=860, min_size=(980, 660), background_color="#030508",
        fullscreen=_fullscreen, text_select=True,
    )
    webview.start(debug=bool(os.environ.get("NEXUS_DEBUG")))
    llm.unload()  # window closed: give the VRAM back to games and other apps
    log.info("NEXUS closed")


def _daily_backup():
    from . import backup

    try:
        path = backup.auto_daily()
        if path:
            log.info(f"daily backup: {path.name}")
    except Exception:
        log.exception("daily backup failed")
