"""Desktop window (pywebview) and the API exposed to the interface."""
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta

import webview

from . import __version__, assistant, bridge, control, i18n, knowledge, llm, memory, profile, scheduler, tools
from .config import WEB_DIR, settings
from .db import db
from .i18n import LANGS, detect, lang

SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+|\n+")
_window: webview.Window | None = None
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

        self._brain = assistant.Assistant(self._on_brain_event, control_hook=self._speech_control)
        self._speaker = Speaker(lambda s: emit("voice", s), lambda payload: emit("speak_env", payload))
        self._listener = Listener(self._on_voice_text, lambda s: emit("voice", s), self._speaker,
                                  on_level=lambda level: emit("mic_level", level))
        scheduler.start(self._on_alert)
        bridge.start(settings["bridge_port"], self._on_profile)
        self._tts_buf, self._tts_streamed, self._reply_lang = "", False, None
        self.ai_state = "cold"  # cold | warming | ready | offline

    def _on_alert(self, alert):
        emit("alert", alert)
        self._speaker.say(alert["text"], remember=False)

    def _on_brain_event(self, event, payload):
        """Forward to the UI and speak while the answer is still being generated (sentence by sentence)."""
        emit(event, payload)
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
                "stt": self._listener.model_state, "version": __version__}

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
        self._speaker.say(text)
        return text

    # -- modes and dock buttons ------------------------------------------------
    def _sync_listening(self):
        """Audio mode with the mic unmuted = continuous conversation; otherwise the mic is closed."""
        self._listener.set_live(settings["ui_mode"] == "audio" and not settings["mic_muted"])

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
        return self.state()

    def set_temporary(self, on):
        """Right rail: temporary conversation - kept only in RAM, never saved, nothing learned automatically."""
        self._speaker.stop()
        memory.set_temporary(bool(on))
        return self.state()

    def state(self):
        return {"ui_mode": settings["ui_mode"], "mic_muted": settings["mic_muted"],
                "voice_enabled": settings["voice_enabled"], "stt": self._listener.model_state,
                "stt_error": self._listener.model_error, "ai_mode": settings["ai_mode"],
                "temporary": memory.temporary}

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

    def _handle_control(self, action):
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
            threading.Thread(target=self._brain.ask, args=(i18n.t("clearer_request"),), daemon=True).start()

    def send(self, text, spoken=False):
        action = control.detect(text)
        if action:
            self._handle_control(action)
            return {"control": action}
        self._reply_lang = detect(text) or lang()
        threading.Thread(target=self._brain.ask, args=(text, spoken), daemon=True).start()
        return {"control": None}

    def history(self):
        return memory.history(settings["history_turns"])

    def clear_history(self):
        memory.clear_history()

    def stop_speaking(self):
        self._speaker.stop()

    def list_voices(self):
        return {"voices": self._speaker.list_voices(), "error": self._speaker.error}

    def test_voice(self, text):
        """Speak a sample with the current voice settings, even if the AI voice is muted."""
        self._speaker.stop()
        self._speaker.say(text, force=True, remember=False)

    def push_to_talk(self):
        if not self._listener.ensure_model():  # first use downloads the Whisper model
            return {"ok": False, "error": self._listener.model_error or "loading"}
        self._listener.push_to_talk()
        return {"ok": True}

    def _on_voice_text(self, text, during_speech=False):
        action = control.detect(text)
        if action:
            emit("heard", {"text": text, "control": action})
            self._handle_control(action)
        elif not during_speech:  # while NEXUS talks only control commands count (echo protection)
            emit("heard", {"text": text})
            self._reply_lang = detect(text) or lang()
            threading.Thread(target=self._brain.ask, args=(text, True), daemon=True).start()

    # -- profile ---------------------------------------------------------------
    def _on_profile(self, prof):
        emit("profile", {"profile": prof, "lang": lang()})
        emit("refresh")

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
        return {"settings": dict(settings), "llm": llm.status(), "langs": LANGS, "lang": lang(),
                "voices": self._speaker.voices}

    def save_settings(self, changes):
        restart_stt = changes.get("stt_model", settings["stt_model"]) != settings["stt_model"]
        new_calendar = changes.get("calendar_ics_url", settings["calendar_ics_url"]) != settings["calendar_ics_url"]
        settings.apply(changes)
        if new_calendar and settings["calendar_ics_url"].strip():
            threading.Thread(target=lambda: (tools.sync_calendar(), emit("refresh")), daemon=True).start()
        if restart_stt:
            self._listener.reload_model()
        return self.get_settings()


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

        report["stt"] = {"ok": True, "input_device": sd.query_devices(kind="input")["name"]}
    except Exception as exc:
        report["stt"] = {"ok": False, "error": repr(exc)}
    (DATA_DIR / "selftest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    return report


def main():
    global _window
    if "--selftest" in sys.argv:
        selftest()
        return
    api = Api()
    _window = webview.create_window(
        "N.E.X.U.S", str(WEB_DIR / "index.html"), js_api=api,
        width=1360, height=860, min_size=(980, 660), background_color="#030508",
    )
    webview.start(debug=bool(os.environ.get("NEXUS_DEBUG")))
    llm.unload()  # window closed: give the VRAM back to games and other apps
