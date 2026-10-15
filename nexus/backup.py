"""Backups (v0.13): a daily automatic copy on start (last 7 kept) and manual backup/restore in Settings > Data.
A backup is a .zip with a consistent copy of the database (SQLite backup API, safe while NEXUS runs) and the
settings (the API key inside stays encrypted). Restoring is applied on the next start, before the database opens."""
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path

from .config import BACKUP_DIR, DB_PATH, RESTORE_PENDING, SETTINGS_PATH

KEEP_AUTO = 7


def create(dest: Path | None = None, auto: bool = False) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = dest or BACKUP_DIR / f"nexus-{'auto' if auto else 'backup'}-{stamp}.zip"
    tmp = BACKUP_DIR / f".db-{stamp}.tmp"
    src = sqlite3.connect(DB_PATH)
    try:
        out = sqlite3.connect(tmp)
        with out:
            src.backup(out)
        out.close()
    finally:
        src.close()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, "nexus.db")
        if SETTINGS_PATH.exists():
            z.write(SETTINGS_PATH, "settings.json")
        z.writestr("NEXUS-BACKUP.txt", f"N.E.X.U.S backup {stamp}\n")
    tmp.unlink()
    if auto:
        for old in sorted(BACKUP_DIR.glob("nexus-auto-*.zip"))[:-KEEP_AUTO]:
            old.unlink()
    return dest


def auto_daily() -> Path | None:
    """One automatic backup per day, the first time NEXUS opens that day."""
    today = time.strftime("%Y%m%d")
    if any(BACKUP_DIR.glob(f"nexus-auto-{today}-*.zip")) or not DB_PATH.exists():
        return None
    return create(auto=True)


def listing() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    return [{"name": p.name, "size": p.stat().st_size, "path": str(p)}
            for p in sorted(BACKUP_DIR.glob("nexus-*.zip"), reverse=True)]


def schedule_restore(path: str) -> dict:
    """Validate a backup and stage it for the next start."""
    try:
        with zipfile.ZipFile(path) as z:
            if "nexus.db" not in z.namelist():
                return {"ok": False, "error": "not a NEXUS backup (nexus.db missing)"}
            head = z.read("nexus.db")[:16]
            if head != b"SQLite format 3\x00":
                return {"ok": False, "error": "the database inside the backup is damaged"}
    except (OSError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)}
    shutil.copy2(path, RESTORE_PENDING)
    return {"ok": True}
