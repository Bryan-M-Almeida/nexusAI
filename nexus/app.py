"""Desktop window (pywebview) and the API exposed to the interface."""
import json
import os
import sys
import threading
from datetime import datetime, timedelta

import webview

from . import assistant, bridge, knowledge, llm, memory, profile, scheduler, tools
from .config import WEB_DIR, settings
from .db import db
from .i18n import LANGS, lang

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
        self._brain = assistant.Assistant(emit)
        from .voice import Listener, Speaker

        self._speaker = Speaker(lambda s: emit("voice", s))
        self._listener = Listener(self._on_voice_text, lambda s: emit("voice", s), self._speaker)
        scheduler.start(self._on_alert)
        bridge.start(settings["bridge_port"], self._on_profile)

    def _on_alert(self, alert):
        emit("alert", alert)
        self._speaker.say(alert["text"])

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
        step("voice", self._listener.model_state != "error", f"{settings['stt_model']} · {self._listener.model_state}")
        if settings["wake_mode"]:
            self._listener.set_wake_mode(True)
        return {"profile": db.get_profile(), "lang": lang(), "llm": st, "settings": dict(settings)}

    def greet(self):
        text = assistant.greeting()
        self._speaker.say(text)
        return text

    # -- conversation ----------------------------------------------------------
    def send(self, text, spoken=False):
        threading.Thread(target=self._brain.ask, args=(text, spoken), daemon=True).start()

    def history(self):
        return memory.history(settings["history_turns"])

    def clear_history(self):
        memory.clear_history()

    def speak(self, text):
        self._speaker.say(text)

    def stop_speaking(self):
        self._speaker.stop()

    def list_voices(self):
        return {"voices": self._speaker.list_voices(), "error": self._speaker.error}

    def test_voice(self, text):
        """Speak a sample with the current voice settings, even if "speak replies" is off."""
        self._speaker.stop()
        self._speaker.say(text, force=True)

    def push_to_talk(self):
        if not self._listener.ensure_model():  # first use downloads the Whisper model
            return {"ok": False, "error": self._listener.model_error or "loading"}
        self._listener.push_to_talk()
        return {"ok": True}

    def set_wake_mode(self, enabled):
        settings.apply({"wake_mode": enabled})
        self._listener.set_wake_mode(bool(enabled))

    def _on_voice_text(self, text):
        emit("heard", text)
        self.send(text, spoken=True)

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
        settings.apply(changes)
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
