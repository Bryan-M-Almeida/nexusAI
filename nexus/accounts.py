"""Local accounts and guest mode (v0.19.0).

Every account has its own data folder - memories, conversations, schedule, settings, backups - so people sharing a
PC never see each other's data:
  - the first account ("owner") keeps the data folder NEXUS always used (nothing is moved);
  - other accounts live in <data>/users/<id>/;
  - a guest gets a temporary folder that is deleted when NEXUS closes (nothing is left behind).
A password is optional. Only a salted scrypt hash is stored (never the password). While an account with a password
is locked, the interface shows only the login screen and the app refuses every data call (see app.Api).
Switching accounts restarts NEXUS in the other folder: every module reads its paths at start, so a restart is the
only way to be sure nothing of the previous account stays in memory."""
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from .config import DATA_DIR

# The root is the folder of the owner account; NEXUS_ACCOUNT_ROOT is set when NEXUS restarts into another account.
ROOT = Path(os.environ.get("NEXUS_ACCOUNT_ROOT") or DATA_DIR)
FILE = ROOT / "accounts.json"
USERS_DIR = ROOT / "users"
ACTIVE = os.environ.get("NEXUS_ACCOUNT", "owner")  # account of this process
GUEST = ACTIVE == "guest"
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}  # ~50 ms per check: cheap for us, slow for guessing


def _load() -> dict:
    try:
        data = json.loads(FILE.read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("accounts", [])
    if not any(a["id"] == "owner" for a in data["accounts"]):
        data["accounts"].insert(0, {"id": "owner", "name": "", "hash": "", "salt": "", "created": time.strftime("%Y-%m-%d")})
    return data


def _save(data: dict):
    FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def _hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), **SCRYPT).hex()


def folder(account_id: str) -> Path:
    return ROOT if account_id == "owner" else USERS_DIR / account_id


def public(acc: dict) -> dict:
    return {"id": acc["id"], "name": acc.get("name") or "", "has_password": bool(acc.get("hash")),
            "created": acc.get("created", ""), "active": acc["id"] == ACTIVE}


def list_accounts() -> list[dict]:
    return [public(a) for a in _load()["accounts"]]


def get(account_id: str) -> dict | None:
    return next((a for a in _load()["accounts"] if a["id"] == account_id), None)


def create(name: str, password: str = "") -> dict:
    name = str(name).strip()[:40]
    if not name:
        return {"ok": False, "error": "name"}
    if password and len(password) < 4:
        return {"ok": False, "error": "short"}
    data = _load()
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "user"
    aid, n = base, 2
    while any(a["id"] == aid for a in data["accounts"]) or aid in ("owner", "guest"):
        aid, n = f"{base}-{n}", n + 1
    acc = {"id": aid, "name": name, "salt": "", "hash": "", "created": time.strftime("%Y-%m-%d")}
    if password:
        acc["salt"] = secrets.token_hex(16)
        acc["hash"] = _hash(password, acc["salt"])
    data["accounts"].append(acc)
    _save(data)
    folder(aid).mkdir(parents=True, exist_ok=True)
    return {"ok": True, "account": public(acc)}


def set_password(account_id: str, old: str, new: str) -> dict:
    data = _load()
    acc = next((a for a in data["accounts"] if a["id"] == account_id), None)
    if not acc:
        return {"ok": False, "error": "unknown"}
    if acc.get("hash") and not check(account_id, old):
        return {"ok": False, "error": "wrong"}
    if new and len(new) < 4:
        return {"ok": False, "error": "short"}
    acc["salt"] = secrets.token_hex(16) if new else ""
    acc["hash"] = _hash(new, acc["salt"]) if new else ""
    _save(data)
    return {"ok": True}


def rename(account_id: str, name: str) -> dict:
    data = _load()
    for a in data["accounts"]:
        if a["id"] == account_id:
            a["name"] = str(name).strip()[:40]
    _save(data)
    return {"ok": True}


_fails: dict[str, list[float]] = {}


def check(account_id: str, password: str) -> bool:
    """Constant-time comparison; after 5 wrong tries in a minute the account waits (slows down guessing)."""
    acc = get(account_id)
    if not acc:
        return False
    if not acc.get("hash"):
        return True
    recent = [t for t in _fails.get(account_id, []) if time.time() - t < 60]
    if len(recent) >= 5:
        return False
    ok = hmac.compare_digest(_hash(str(password), acc["salt"]), acc["hash"])
    if not ok:
        _fails[account_id] = recent + [time.time()]
    return ok


def throttled(account_id: str) -> bool:
    return len([t for t in _fails.get(account_id, []) if time.time() - t < 60]) >= 5


def delete(account_id: str, password: str) -> dict:
    """Remove another account and its whole folder (never the owner, never the open one)."""
    if account_id in ("owner", ACTIVE):
        return {"ok": False, "error": "protected"}
    if not check(account_id, password):
        return {"ok": False, "error": "wrong"}
    data = _load()
    data["accounts"] = [a for a in data["accounts"] if a["id"] != account_id]
    _save(data)
    shutil.rmtree(folder(account_id), ignore_errors=True)
    return {"ok": True}


def guest_folder() -> Path:
    return Path(tempfile.mkdtemp(prefix="nexus-guest-"))


HANDOFF = ROOT / ".handoff"


def _handoff_ok() -> bool:
    """The previous NEXUS process already checked the password: a one-time token, valid for 30 s, read once."""
    token = os.environ.get("NEXUS_HANDOFF", "")
    try:
        saved = json.loads(HANDOFF.read_text("utf-8"))
    except (OSError, ValueError):
        return False
    HANDOFF.unlink(missing_ok=True)
    return bool(token) and hmac.compare_digest(saved.get("token", ""), token) and saved.get("account") == ACTIVE \
        and time.time() < saved.get("until", 0)


_skip_login = None


def needs_login() -> bool:
    """Ask who is using NEXUS at start only when there is a choice or a password to protect."""
    global _skip_login
    if _skip_login is None:
        _skip_login = GUEST or _handoff_ok()
    if _skip_login:
        return False
    accs = _load()["accounts"]
    me = get(ACTIVE)
    return len(accs) > 1 or bool(me and me.get("hash"))


def relaunch_env(account_id: str, unlocked: bool) -> dict:
    """Environment of the NEXUS process that opens another account (or the guest)."""
    env = {**os.environ, "NEXUS_ACCOUNT_ROOT": str(ROOT), "NEXUS_ACCOUNT": account_id, "NEXUS_RELAUNCH": "1"}
    env.pop("NEXUS_HANDOFF", None)
    if account_id == "guest":
        env["NEXUS_HOME"] = str(guest_folder())
    else:
        env["NEXUS_HOME"] = str(folder(account_id))
        if unlocked:  # the password was checked in this process: don't ask twice
            token = secrets.token_hex(16)
            HANDOFF.write_text(json.dumps({"token": token, "account": account_id, "until": time.time() + 30}), "utf-8")
            env["NEXUS_HANDOFF"] = token
    return env
