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
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
RESTORE_PENDING = DATA_DIR / "restore_pending.zip"


def _apply_pending_restore():
    """A backup chosen in Settings > Data is applied here, on the next start, BEFORE the database is opened
    (replacing an open SQLite file is unsafe). The current data is kept in backups/before-restore-*."""
    if not RESTORE_PENDING.exists():
        return
    import shutil
    import time
    import zipfile

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    keep = BACKUP_DIR / f"before-restore-{time.strftime('%Y%m%d-%H%M%S')}"
    keep.mkdir()
    for name in ("nexus.db", "nexus.db-wal", "nexus.db-shm", "settings.json"):
        if (DATA_DIR / name).exists():
            shutil.move(str(DATA_DIR / name), str(keep / name))
    with zipfile.ZipFile(RESTORE_PENDING) as z:
        for member in ("nexus.db", "settings.json"):
            if member in z.namelist():
                (DATA_DIR / member).write_bytes(z.read(member))
    RESTORE_PENDING.unlink()


_apply_pending_restore()
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
    "network_mode": "auto",       # auto (by measured speed) | offline | hybrid (local AI + online services) | online
    "performance": "balanced",    # economy | balanced | max ("Força total", only if the hardware allows)
    "stt_beam": 5,                # Whisper beam size (1 = fastest)
    "llm_keep_alive": "2h",       # how long the model stays in VRAM after the last message
    "llm_num_gpu": -1,            # layers on the GPU (-1 = Ollama decides, 999 = all, 0 = CPU only)
    # v0.14 ----------------------------------------------------------------------------------------------------
    "bg_wake_only": True,         # window minimized/unfocused: only utterances starting with "Nexus" count
    "bg_release_minutes": 10,     # minimized this long with the mic off -> Whisper leaves memory
    "pause_when_unfocused": True, # stop the ring/HUD animations while the window isn't in focus
    "ai_target": "local",         # local | api (one-click switch keeps both configurations)
    "ai_local": {},               # saved llm_* fields for each target
    "ai_api": {},
    # v0.15.5: user mode shows the core; beta features are opt-in (Settings > Beta). Developer mode = everything on.
    "app_mode": "user",           # user | developer
    "beta_workspace": False,
    "beta_library": False,
    "beta_skills": False,
    "beta_browser": False,
    # v0.16.1 layout: "computer" (menus for the mouse) or "shortcuts" (nothing on screen: shortcuts + voice only)
    "ui_layout": "computer",
    "bar_top": "hover",           # each menu: hover (appears at the screen edge) | fixed | off
    "bar_left": "hover",
    "bar_right": "hover",
    "bar_bottom": "hover",
    "ring_wander": True,
    # v0.16.5
    "show_exchange": True,        # the last exchange under the ring (Ctrl+I shows it for a moment when off)
    "exchange_follow": False,     # the text moves with the ring (drag and wandering) instead of staying put
    "exchange_hide_seconds": 45,  # waiting this long, the text under the ring fades (0 = never)
    "cursor_style": "ring",       # system | ring | dot | arrow (NEXUS cursors take the ring colour)
    "cursor_size": "medium",      # small | medium | large
    "shortcuts": {},              # action id -> key combination chosen by the user (Settings > Shortcuts)
    "tutorial_done": False,       # first run: NEXUS narrates a short tutorial
    # v0.18.0: integrations hub, media, apps
    "connectors": {},             # integration id -> on/off (missing = on)
    "custom_connectors": [],      # the user's own integrations: {id, name, keywords, url, ttl_min, on}
    "home_currency": "",          # "" = by language (BRL / USD)
    "home_country": "",           # holidays; "" = by language (BR / US / ES)
    "music_player": "youtube",    # youtube | youtube music | spotify | limusic
    "beta_media": False,
    "beta_apps": False,
    "apps_suspend": "games",      # games (suspend when NEXUS opens a game) | never
    "game_watch": False,          # also suspend when a game started elsewhere comes to the foreground
    "apps_games": [],             # app names the user marked as games
    "apps_work": [],              # app names the user marked as work apps
    # v0.18.5: Settings > Personalisation (the AI can change these when asked: nexus/prefs.py)
    "theme": "nexus",             # nexus | amd | emerald | violet | amber | graphite | ice (sets the three colours)
    "ring_scale": 100,            # ring size, % (60-140)
    "ring_speed": "normal",       # slow | normal | fast
    "exchange_size": 14,          # px of the text under the ring
    "bg_style": "glow",           # glow | solid | grid
    "font_brand": "orbitron",     # orbitron (futuristic) | clean
    "vagalume_key": "",           # v0.19.6: optional free key of Vagalume's official API (lyrics)
    "center_style": "ring",       # v0.19.6: ring | pet (the NEXUS orb) in the centre of the screen
    "system_check_done": False,   # v0.19.0: the first start checks every system and says the result once
    # v0.16.8
    "speak_menus": True,          # NEXUS says which menu it opened ("Abrindo as configurações")
    "beta_map": False,            # concept map (skills and knowledge around the ring) - beta
    "beta_hold_talk": False,      # hold the talk key to speak, release to send - beta
    # v0.17.5 beta features
    "beta_training": False,       # training mode + "Aprendizados" tab
    "beta_memory_import": False,  # import memories from other AIs (ChatGPT, Claude, Gemini...)
    # v0.17.0: Terms of Use / Privacy Policy accepted (version and when)
    "terms_version": "",
    "terms_accepted_at": "",          # the ring drifts around the screen by itself
    "rest_minutes": 3,            # no interaction for this long: texts hide, only the ring plays (0 = never)
    # v0.16 interface colours (ring, core, background)
    "color_ring": "#cfe4ff",
    "color_core": "#2f86ff",
    "color_bg": "#0b1f5c",
    "llm_raw_prompt": False,      # experimental: qwen3 prompt written by NEXUS (raw) - same speed in v0.15.5 tests
}


# API keys are stored encrypted with Windows DPAPI (bound to this Windows user), never as plain text (v0.13).
_KEY_PREFIX = "dpapi:"


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    src = BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if encrypt:
        ok = fn(ctypes.byref(src), "NEXUS", None, None, None, 0x1, ctypes.byref(out))  # 0x1: no UI
    else:
        ok = fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI failed")
    result = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return result


def protect(secret: str) -> str:
    import base64

    if not secret or secret == "ollama" or secret.startswith(_KEY_PREFIX) or sys.platform != "win32":
        return secret
    try:
        return _KEY_PREFIX + base64.b64encode(_dpapi(secret.encode("utf-8"), True)).decode()
    except Exception:
        return secret


def unprotect(value: str) -> str:
    import base64

    if not str(value).startswith(_KEY_PREFIX):
        return value
    try:
        return _dpapi(base64.b64decode(value[len(_KEY_PREFIX):]), False).decode("utf-8")
    except Exception:
        return ""  # another Windows user / machine: the key must be typed again


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        if SETTINGS_PATH.exists():
            try:
                self.update(json.loads(SETTINGS_PATH.read_text("utf-8")))
            except json.JSONDecodeError:
                pass
        self["llm_api_key"] = unprotect(self["llm_api_key"])
        if SETTINGS_PATH.exists() and '"tutorial_done"' not in SETTINGS_PATH.read_text("utf-8"):
            self["tutorial_done"] = True  # existing installs skip the first-run tutorial (it can be opened anytime)
            self.save()
        if not self.get("v15_auto_net"):  # v0.15: the automatic connection mode becomes the default once
            if self.get("network_mode") == "hybrid":
                self["network_mode"] = "auto"
            self["v15_auto_net"] = True
            if SETTINGS_PATH.exists():
                self.save()
        for slot in ("ai_local", "ai_api"):  # v0.14: the saved API configuration keeps its key encrypted too
            if isinstance(self.get(slot), dict) and self[slot].get("llm_api_key"):
                self[slot] = {**self[slot], "llm_api_key": unprotect(self[slot]["llm_api_key"])}
        if self["llm_api_key"] not in ("", "ollama") and '"dpapi:' not in SETTINGS_PATH.read_text("utf-8"):
            self.save()  # a key saved as plain text by v0.10-v0.12 is encrypted now

    def save(self):
        data = {**self, "llm_api_key": protect(self["llm_api_key"])}
        for slot in ("ai_local", "ai_api"):
            if isinstance(data.get(slot), dict) and data[slot].get("llm_api_key"):
                data[slot] = {**data[slot], "llm_api_key": protect(data[slot]["llm_api_key"])}
        SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

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
