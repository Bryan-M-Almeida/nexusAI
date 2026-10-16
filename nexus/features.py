"""Beta features and app modes (v0.15.5). The core of NEXUS (voice, chat, memory, schedule, reminders, knowledge,
conversations, files, focus, emergency) is always on. Newer or riskier areas are "beta": off by default for users
until the final version, each one enabled in Settings > Beta knowing it may have bugs. Developer mode turns every
feature on (used to test everything). Disabled features also leave the AI's tool list, so the prompt gets smaller."""
from .config import settings

# id -> tools that belong to it (removed from the AI's tool list while the feature is off)
BETA = {
    "workspace": set(),            # isolated project area: files + confirmed commands (tools only exist inside it)
    "library": {"list_books", "read_book"},
    "skills": set(),  # (open_interface checks library/workspace/skills itself)
    "browser": {"open_url", "web_search", "play_music"},
    "map": set(),        # v0.16.8: concept map of skills and knowledge
    "hold_talk": set(),  # v0.16.8: hold the talk key to speak
    "training": set(),       # v0.17.5: training mode + "Aprendizados" tab
    "memory_import": set(),  # v0.17.5: import memories from other AIs
    "media": {"media_control"},  # v0.18.0: play/pause, next, volume, what's playing (Spotify, LiMusic, browser...)
    "apps": {"open_app"},        # v0.18.0: open installed apps; games suspend NEXUS
}
TOOL_FEATURE = {tool: feat for feat, tools in BETA.items() for tool in tools}


def developer() -> bool:
    return settings.get("app_mode") == "developer"


def enabled(feature: str) -> bool:
    if feature not in BETA:
        return True  # core features are always on
    return developer() or bool(settings.get("beta_" + feature, False))


def tool_allowed(name: str) -> bool:
    feat = TOOL_FEATURE.get(name)
    return feat is None or enabled(feat)


def state() -> dict:
    return {"mode": "developer" if developer() else "user", "features": {f: enabled(f) for f in BETA}}
