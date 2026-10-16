"""Terms of Use and Privacy Policy (v0.17.0). The texts live in web/legal.js (PT/EN/ES); this module only knows the
version the user accepted. Until the current version is accepted NEXUS doesn't open the microphone, doesn't measure
the internet connection and doesn't load web fonts - nothing leaves the computer and nothing is captured."""
from datetime import datetime

from .config import settings

VERSION = "1.1"   # bump when the texts change in substance: everybody is asked again
DATE = "2026-10-16"


def accepted() -> bool:
    return settings.get("terms_version") == VERSION


def accept() -> dict:
    settings.apply({"terms_version": VERSION, "terms_accepted_at": datetime.now().isoformat(timespec="seconds")})
    return state()


def revoke() -> dict:
    settings.apply({"terms_version": "", "terms_accepted_at": ""})
    return state()


def state() -> dict:
    return {"accepted": accepted(), "version": VERSION, "date": DATE, "accepted_at": settings.get("terms_accepted_at", "")}
