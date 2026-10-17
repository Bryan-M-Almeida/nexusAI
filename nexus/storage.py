"""Settings > Data > Storage (v0.19.0): how much space NEXUS uses, item by item - the database (and how many
memories, messages, documents...), backups, logs, books, workspaces, the integrations cache, the voice models, the AI
models and the program itself - plus the free space on the disk. The interface refreshes it every few seconds while
it is open, so the numbers change live (a download growing, a backup being written)."""
import os
import shutil
import sys
from pathlib import Path

from .config import BACKUP_DIR, DATA_DIR, DB_PATH, LOG_DIR, PKG_DIR


def _size(path: Path) -> tuple[int, int]:
    """(bytes, files) of a file or a folder."""
    if not path.exists():
        return 0, 0
    if path.is_file():
        return path.stat().st_size, 1
    total = count = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            full = os.path.join(root, f)
            if os.path.islink(full):  # the Hugging Face cache links each file to its blob: count the blob once
                continue
            try:
                total += os.path.getsize(full)
                count += 1
            except OSError:
                pass
    return total, count


def _tables() -> list[dict]:
    """Rows of the main tables (what is inside the database)."""
    from .db import db

    out = []
    for table, key in (("memories", "memories"), ("messages", "messages"), ("conversations", "conversations"),
                       ("kb_docs", "documents"), ("kb_chunks", "chunks"), ("tasks", "tasks"), ("events", "events"),
                       ("notes", "notes"), ("records", "records"), ("actions", "actions"), ("trainings", "trainings"),
                       ("notifications", "notifications")):
        try:
            out.append({"key": key, "rows": db.one(f"SELECT COUNT(*) AS n FROM {table}")["n"]})
        except Exception:  # a table of a feature that never ran
            continue
    return out


def _voice_models() -> list[dict]:
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
    except Exception:
        return []
    out = []
    for d in sorted(Path(HF_HUB_CACHE).glob("models--Systran--faster-whisper-*")):
        size, _ = _size(d)
        out.append({"name": d.name.split("faster-whisper-")[-1], "bytes": size})
    from .voice import bundled_model

    for name in ("tiny", "base", "small", "medium"):
        d = bundled_model(name)
        if d:
            out.append({"name": name + " (NEXUS)", "bytes": _size(d)[0]})
    return out


def _ai_models() -> list[dict]:
    import httpx

    from . import llm

    try:
        tags = httpx.get(f"{llm._ollama_root()}/api/tags", timeout=3).json().get("models", [])
    except Exception:
        return []
    return [{"name": t.get("name", ""), "bytes": int(t.get("size") or 0)} for t in tags]


def report(with_models: bool = True) -> dict:
    db_bytes = sum(_size(Path(str(DB_PATH) + ext))[0] for ext in ("", "-wal", "-shm"))
    parts = []
    for key, path in (("library", DATA_DIR / "library"), ("workspaces", DATA_DIR / "workspaces"),
                      ("backups", BACKUP_DIR), ("logs", LOG_DIR), ("reports", DATA_DIR / "reports"),
                      ("inbox", DATA_DIR / "inbox"), ("cache", DATA_DIR / "cache"), ("temp", DATA_DIR / "tmp")):
        size, files = _size(path)
        parts.append({"key": key, "bytes": size, "files": files})
    data_total = _size(DATA_DIR)[0]
    program = Path(sys.executable).parent if getattr(sys, "frozen", False) else PKG_DIR
    disk = shutil.disk_usage(DATA_DIR)
    out = {"data_dir": str(DATA_DIR), "data_bytes": data_total, "db_bytes": db_bytes, "tables": _tables(), "parts": parts,
           "program_bytes": _size(program)[0], "disk_free": disk.free, "disk_total": disk.total}
    if with_models:
        out["voice_models"] = _voice_models()
        out["ai_models"] = _ai_models()
    return out
