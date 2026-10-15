"""Paths and user settings."""
import json
import os
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
WEB_DIR = PKG_DIR / "web"
SEED_DIR = PKG_DIR / "seed"


def _data_dir() -> Path:
    # Installed (frozen) builds write to %LOCALAPPDATA%\NEXUS; dev runs use ./data.
    if env := os.environ.get("NEXUS_HOME"):
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NEXUS"
    return PKG_DIR.parent / "data"


DATA_DIR = _data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "nexus.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
INBOX_DIR = DATA_DIR / "inbox"  # drop .md/.txt/.pdf/.json here to be learned on boot
INBOX_DIR.mkdir(exist_ok=True)

DEFAULTS = {
    # Any OpenAI-compatible server: Ollama (http://127.0.0.1:11434/v1) or LM Studio (http://127.0.0.1:1234/v1)
    "llm_base_url": "http://127.0.0.1:11434/v1",
    "llm_model": "qwen3:8b",          # best tool use that fits 8 GB VRAM (qwen2.5:7b skipped tool calls in tests)
    "llm_api_key": "ollama",
    "llm_provider": "auto",       # auto (Ollama native API when the URL is :11434) | ollama | openai
    "llm_context": 8192,          # context window requested from Ollama (its default 4096 truncates the tools)
    "llm_temperature": 0.3,
    "ai_mode": "assistant",       # assistant (complete, friendly) | direct (shortest exact answer, faster)
    "auto_memory": True,          # extract facts about the user after each exchange
    "voice_enabled": True,        # speak replies
    "voice_gender": "male",       # male | female (falls back to the other voice with shifted pitch)
    "voice_effect": "jarvis",     # jarvis (subtle synthetic) | robot (strong) | none
    "tts_speed": 0,               # SAPI speed -10..10
    "stt_model": "small",         # faster-whisper size: tiny | base | small | medium
    "language": "auto",           # auto (from profile) | pt | en | es
    "wake_word": "nexus",
    "ui_mode": "audio",           # audio (ring only, voice conversation) | text (messages only)
    "mic_muted": False,           # in audio mode the mic listens continuously unless muted
    "require_wake_word": False,   # only accept utterances that start with "Nexus"
    "integrations": True,         # weather, news, currency, Wikipedia, calendar (internet, no accounts/keys)
    "home_city": "",              # default city for the weather
    "calendar_ics_url": "",       # read-only calendar feed (Google Calendar "secret address in iCal format")
    "bridge_port": 47800,         # local endpoint the landing page form can POST the profile to
    "history_turns": 12,
    # v0.10 -------------------------------------------------------------------------------------------------
    "llm_preset": "ollama",       # Settings > AI provider preset (fills URL; "custom" = edit freely)
    "auto_title": True,           # the AI writes each conversation's title/description in the background
    "greet_on_start": True,       # speak the greeting when the app opens
    "start_fullscreen": True,
    "tts_volume": 100,            # 0..100
    "mic_device": "",             # input device name; "" = Windows default (NX-VOZ-002)
    "vad_threshold": 0.5,         # speech probability that opens a recording (Silero)
    "vad_silence": 0.7,           # seconds of silence that close it
    "reminder_leads": "60,10,0",  # minutes before events/tasks to remind (0 = at the time)
    "speak_reminders": True,      # say reminders aloud even in text mode (unless the AI voice is muted)
    "desktop_notifications": True,  # Windows notifications
    "notify_sound": True,         # short chime in the app
    "quiet_hours": "",            # e.g. "22:00-07:00": reminders are only listed, never spoken or popped up
    "daily_briefing": "",         # e.g. "08:00": once a day, a spoken summary of today's agenda and tasks
    "show_hud": True,             # telemetry, corners and pulse around the ring
    "show_captions": True,        # audio mode: the reply as a caption while it is generated
    "reduce_motion": False,       # stops the ring animations (low-end PCs / preference)
    # v0.11 ----------------------------------------------------------------------------------------------------
    "focus_mode": False,          # no distractions: reminders only in the bell, minimal interface
    "focus_in_workspace": True,   # focus mode turns on by itself while a workspace is open
    # v0.12 ----------------------------------------------------------------------------------------------------
    "network_mode": "hybrid",     # offline (nothing leaves the PC) | hybrid (local AI + online services) | online
    "performance": "balanced",    # economy | balanced | max ("Força total", only if the hardware allows)
    "stt_beam": 5,                # Whisper beam size (1 = fastest)
    "llm_keep_alive": "2h",       # how long the model stays in VRAM after the last message
    "llm_num_gpu": -1,            # layers on the GPU (-1 = Ollama decides, 999 = all, 0 = CPU only)
}


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        if SETTINGS_PATH.exists():
            try:
                self.update(json.loads(SETTINGS_PATH.read_text("utf-8")))
            except json.JSONDecodeError:
                pass

    def save(self):
        SETTINGS_PATH.write_text(json.dumps(self, indent=2, ensure_ascii=False), "utf-8")

    def apply(self, changes: dict):
        for k, v in changes.items():
            if k not in DEFAULTS:
                continue
            kind = type(DEFAULTS[k])
            if kind is bool and not isinstance(v, bool):
                v = str(v).lower() in ("1", "true", "on", "sim", "yes")
            self[k] = kind(v)
        self.save()


settings = Settings()
