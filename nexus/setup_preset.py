"""Choices made in the installer (v0.20.5), applied once on the first start of the main account.

The installer (installer/nexus.iss) writes %LOCALAPPDATA%\\NEXUS\\install_preset.json and, when the user picked one,
install_profile.json (the profile JSON). NEXUS applies them through the same validation as the Settings screen,
then renames the preset so it never runs again."""
import json

from . import accounts, models, prefs, profile
from .config import DATA_DIR, settings
from .logs import log

PRESET = DATA_DIR / "install_preset.json"
PROFILE = DATA_DIR / "install_profile.json"
LANGS = {"pt", "en", "es"}


def apply() -> dict:
    """Returns what was applied ({} when there is nothing to do)."""
    if accounts.GUEST or accounts.ACTIVE != "owner" or not PRESET.exists():
        return {}
    done = {}
    try:
        data = json.loads(PRESET.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        log.warning(f"install preset unreadable: {exc}")
        data = {}
    if data.get("language") in LANGS:
        settings.apply({"language": data["language"]})
        done["language"] = data["language"]
    if data.get("voice_gender") in ("male", "female"):
        settings.apply({"voice_gender": data["voice_gender"]})
        done["voice_gender"] = data["voice_gender"]
    look = {k: data[k] for k in ("theme", "center_style") if data.get(k)}
    if look:
        try:
            done.update(prefs.apply(look))
        except (ValueError, TypeError) as exc:
            log.warning(f"install preset look: {exc}")
    model = data.get("llm_model") or "auto"
    if model == "auto" or model not in models.BY_ID:
        model = models.recommended()
    settings.apply({"llm_model": model, "install_model_pull": model})  # downloaded on the first start (Downloads)
    done["llm_model"] = model
    if PROFILE.exists():
        try:
            done["profile"] = profile.import_profile(PROFILE.read_text("utf-8-sig"))["name"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning(f"install profile not imported: {exc}")
        PROFILE.unlink(missing_ok=True)
    PRESET.replace(PRESET.with_name("install_preset.applied.json"))
    log.info(f"install preset applied: {done}")
    return done
