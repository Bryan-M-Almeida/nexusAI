"""NEXUS workspace (v0.11): an isolated area per project, separate from normal conversations.

- Each workspace has its own folder (DATA_DIR/workspaces/<slug>), conversation, notes and change journal.
- The AI may create, edit, move and delete files freely, but only INSIDE that folder (path jail): absolute paths,
  "..", drive letters and links that lead outside are refused.
- Every write/delete first copies the previous version to .nexus/history, so any change can be undone and the AI
  never silently overwrites its own earlier work (edit_file only replaces an exact, unique snippet).
- Commands (run_command) run inside the folder only after the user confirms each one in the interface.
"""
import json
import re
import shutil
import subprocess
import threading
import unicodedata
from pathlib import Path

from .config import DATA_DIR
from .db import db, now

ROOT = DATA_DIR / "workspaces"
META = ".nexus"           # history + notes, hidden from the AI's file listing
MAX_READ = 60_000         # chars returned by read_file
MAX_WRITE = 400_000       # chars accepted by write_file
COMMAND_TIMEOUT = 120     # seconds
_confirm: dict[str, dict] = {}  # pending command confirmations: id -> {"event", "ok"}

active: dict | None = None  # the open workspace row, or None (normal conversations)


class WorkspaceError(Exception):
    pass


# ---------------------------------------------------------------- workspaces
def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "workspace"


def create(name: str, description: str = "") -> dict:
    name = name.strip()[:60] or "Workspace"
    slug, n = _slug(name), 1
    while (ROOT / slug).exists() or db.one("SELECT id FROM workspaces WHERE folder = ?", (slug,)):
        n += 1
        slug = f"{_slug(name)}-{n}"
    (ROOT / slug / META / "history").mkdir(parents=True, exist_ok=True)
    wid = db.execute("INSERT INTO workspaces(name, description, folder, created, updated) VALUES (?,?,?,?,?)",
                     (name, description.strip()[:400], slug, now(), now())).lastrowid
    db.log_action("área de trabalho", f"Criou a área de trabalho '{name}'")
    return get(wid)


def get(wid: int) -> dict | None:
    return db.one("SELECT * FROM workspaces WHERE id = ?", (int(wid),))


def listing() -> list[dict]:
    rows = db.all("SELECT * FROM workspaces ORDER BY updated DESC")
    for r in rows:
        r["files"] = sum(1 for _ in _walk(root(r))) if root(r).exists() else 0
    return rows


def root(ws: dict | None = None) -> Path:
    ws = ws or active
    if not ws:
        raise WorkspaceError("no workspace is open")
    return (ROOT / ws["folder"]).resolve()


def open_(wid: int) -> dict:
    global active
    ws = get(wid)
    if not ws:
        raise WorkspaceError("workspace not found")
    root(ws).joinpath(META, "history").mkdir(parents=True, exist_ok=True)
    active = ws
    db.execute("UPDATE workspaces SET updated = ? WHERE id = ?", (now(), ws["id"]))
    return ws


def close():
    global active
    active = None


def delete(wid: int):
    """Removes it from the list and moves its folder to workspaces/.trash (never deleted outright)."""
    global active
    ws = get(wid)
    if not ws:
        return
    src = ROOT / ws["folder"]
    if src.exists():
        dest = ROOT / ".trash" / f"{ws['folder']}-{now().replace(':', '')}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
    db.execute("DELETE FROM workspace_changes WHERE workspace_id = ?", (ws["id"],))
    db.execute("DELETE FROM workspaces WHERE id = ?", (ws["id"],))
    if active and active["id"] == ws["id"]:
        active = None


# ---------------------------------------------------------------- path jail
def resolve(path: str) -> Path:
    """Workspace-relative path -> absolute path inside the workspace, or WorkspaceError."""
    raw = str(path or "").strip().replace("\\", "/")
    if not raw or raw in (".", "/"):
        return root()
    if re.match(r"^[a-zA-Z]:", raw) or raw.startswith("//") or raw.startswith("~"):
        raise WorkspaceError(f"'{path}' is outside the workspace: use paths relative to its folder")
    target = (root() / raw.lstrip("/")).resolve()
    if target != root() and root() not in target.parents:
        raise WorkspaceError(f"'{path}' is outside the workspace")
    if META in target.relative_to(root()).parts:
        raise WorkspaceError("the .nexus folder is reserved for NEXUS")
    return target


def rel(p: Path) -> str:
    return p.relative_to(root()).as_posix() or "."


def _walk(base: Path):
    for p in sorted(base.rglob("*")):
        if META in p.relative_to(base).parts:
            continue
        yield p


# ---------------------------------------------------------------- change journal (undo)
def _backup(target: Path, op: str) -> None:
    """Keep the previous version (if any) and log the change."""
    backup = ""
    if target.exists() and target.is_file():
        stamp = now().replace(":", "").replace("-", "")
        dest = root() / META / "history" / f"{stamp}-{db.one('SELECT COUNT(*) n FROM workspace_changes')['n']}" / rel(target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, dest)
        backup = dest.relative_to(root()).as_posix()
    db.execute("INSERT INTO workspace_changes(workspace_id, ts, op, path, backup) VALUES (?,?,?,?,?)",
               (active["id"], now(), op, rel(target), backup))
    db.execute("UPDATE workspaces SET updated = ? WHERE id = ?", (now(), active["id"]))


def changes(limit: int = 30) -> list[dict]:
    return db.all("SELECT * FROM workspace_changes WHERE workspace_id = ? AND undone = 0 ORDER BY id DESC LIMIT ?",
                  (active["id"], limit))


def undo(change_id: int | None = None) -> dict:
    """Undo one change (default: the latest): restore the previous version or remove a file that was created."""
    row = db.one("SELECT * FROM workspace_changes WHERE workspace_id = ? AND undone = 0 "
                 + ("AND id = ?" if change_id else "ORDER BY id DESC LIMIT 1"),
                 (active["id"], int(change_id)) if change_id else (active["id"],))
    if not row:
        return {"ok": False, "error": "nothing to undo"}
    target = root() / row["path"]
    if row["backup"]:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root() / row["backup"], target)
    elif row["op"] in ("create", "mkdir") and target.exists():
        (target.rmdir if target.is_dir() else target.unlink)()
    db.execute("UPDATE workspace_changes SET undone = 1 WHERE id = ?", (row["id"],))
    return {"ok": True, "undone": row["op"], "path": row["path"]}


# ---------------------------------------------------------------- tools for the AI
def list_files(path: str = "."):
    base = resolve(path)
    if not base.exists():
        return {"error": f"'{path}' does not exist"}
    items = []
    for p in (_walk(base) if base.is_dir() else [base]):
        items.append(rel(p) + ("/" if p.is_dir() else f"  ({p.stat().st_size} B)"))
        if len(items) >= 300:
            items.append("... (truncated)")
            break
    return {"files": items or ["(empty)"]}


def read_file(path: str):
    target = resolve(path)
    if not target.is_file():
        return {"error": f"'{path}' is not a file"}
    text = target.read_text(encoding="utf-8", errors="replace")
    return {"path": rel(target), "content": text[:MAX_READ], "truncated": len(text) > MAX_READ}


def write_file(path: str, content: str):
    """Create or overwrite a whole file (the old version goes to the history)."""
    target = resolve(path)
    if target.is_dir():
        return {"error": f"'{path}' is a folder"}
    if len(content or "") > MAX_WRITE:
        return {"error": "content too large"}
    existed = target.exists()
    _backup(target, "write" if existed else "create")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or "", encoding="utf-8")
    return {"ok": True, "path": rel(target), "created": not existed, "chars": len(content or "")}


def edit_file(path: str, old_text: str, new_text: str):
    """Replace an exact snippet that appears exactly once (safer than rewriting the whole file)."""
    target = resolve(path)
    if not target.is_file():
        return {"error": f"'{path}' is not a file"}
    text = target.read_text(encoding="utf-8", errors="replace")
    count = text.count(old_text or "\0")
    if count != 1:
        return {"error": f"old_text found {count} times; it must match exactly once (read the file first)"}
    _backup(target, "edit")
    target.write_text(text.replace(old_text, new_text or ""), encoding="utf-8")
    return {"ok": True, "path": rel(target)}


def make_folder(path: str):
    target = resolve(path)
    if target.exists():
        return {"ok": True, "path": rel(target), "existed": True}
    target.mkdir(parents=True)
    db.execute("INSERT INTO workspace_changes(workspace_id, ts, op, path, backup) VALUES (?,?,?,?,?)",
               (active["id"], now(), "mkdir", rel(target), ""))
    return {"ok": True, "path": rel(target)}


def delete_file(path: str):
    target = resolve(path)
    if target == root():
        return {"error": "cannot delete the workspace itself"}
    if not target.exists():
        return {"error": f"'{path}' does not exist"}
    if target.is_dir():
        if any(target.iterdir()):
            return {"error": "folder is not empty: delete its files first"}
        db.execute("INSERT INTO workspace_changes(workspace_id, ts, op, path, backup) VALUES (?,?,?,?,?)",
                   (active["id"], now(), "rmdir", rel(target), ""))
        target.rmdir()
        return {"ok": True}
    _backup(target, "delete")
    target.unlink()
    return {"ok": True, "path": rel(target)}


def search_files(query: str):
    """Case-insensitive text search in the workspace's text files."""
    q, hits = str(query or "").lower(), []
    for p in _walk(root()):
        if p.is_file() and p.stat().st_size < 2_000_000:
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if q in line.lower():
                        hits.append(f"{rel(p)}:{i}: {line.strip()[:160]}")
                        if len(hits) >= 60:
                            return {"matches": hits, "truncated": True}
            except OSError:
                continue
    return {"matches": hits}


def workspace_note(note: str):
    """Remember something about THIS project only (kept in .nexus/notes.md, never mixed with user memories)."""
    f = root() / META / "notes.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()[:16]} {str(note).strip()}\n")
    return {"ok": True}


def notes() -> str:
    f = root() / META / "notes.md"
    return f.read_text(encoding="utf-8")[-3000:] if f.exists() else ""


def run_command(command: str, ask=None):
    """Run a shell command inside the workspace folder, ONLY after the user confirms it (ask -> bool)."""
    command = str(command or "").strip()
    if not command:
        return {"error": "empty command"}
    if ask is None or not ask(command):
        return {"denied": True, "message": "The user did not allow this command. Do not retry it; ask what to do."}
    try:
        r = subprocess.run(command, shell=True, cwd=root(), capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {COMMAND_TIMEOUT} s"}
    db.execute("INSERT INTO workspace_changes(workspace_id, ts, op, path, backup) VALUES (?,?,?,?,?)",
               (active["id"], now(), "command", command[:200], ""))
    return {"exit_code": r.returncode, "stdout": r.stdout[-6000:], "stderr": r.stderr[-3000:]}


# ---------------------------------------------------------------- confirmations (UI <-> worker thread)
def request_confirmation(cid: str) -> dict:
    _confirm[cid] = {"event": threading.Event(), "ok": False}
    return _confirm[cid]


def answer_confirmation(cid: str, ok: bool):
    item = _confirm.get(cid)
    if item:
        item["ok"] = bool(ok)
        item["event"].set()


def tree_text(limit: int = 120) -> str:
    lines = []
    for p in _walk(root()):
        depth = len(p.relative_to(root()).parts) - 1
        lines.append("  " * depth + p.name + ("/" if p.is_dir() else ""))
        if len(lines) >= limit:
            lines.append("  ...")
            break
    return "\n".join(lines) or "(empty folder)"


def _fn(name, desc, props=None, required=()):
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props or {},
                                                            "required": list(required)}}}


S = {"type": "string"}
P = {"type": "string", "description": "path relative to the workspace folder, e.g. src/main.py"}
SCHEMAS = [
    _fn("list_files", "List files and folders of the workspace (or of a subfolder).", {"path": P}),
    _fn("read_file", "Read a text file of the workspace.", {"path": P}, ["path"]),
    _fn("write_file", "Create or overwrite a whole file in the workspace (previous version is kept for undo).",
        {"path": P, "content": S}, ["path", "content"]),
    _fn("edit_file", "Replace an exact snippet that occurs exactly once in a file. Read the file first.",
        {"path": P, "old_text": S, "new_text": S}, ["path", "old_text", "new_text"]),
    _fn("make_folder", "Create a folder in the workspace.", {"path": P}, ["path"]),
    _fn("delete_file", "Delete a file (kept in history for undo) or an empty folder.", {"path": P}, ["path"]),
    _fn("search_files", "Search text in the workspace files.", {"query": S}, ["query"]),
    _fn("workspace_note", "Remember a decision or fact about THIS project for later sessions.", {"note": S}, ["note"]),
    _fn("undo_change", "Undo the latest change you made to the workspace files.", {}),
    _fn("run_command", "Run a command (e.g. python main.py, pip install x, npm test) inside the workspace folder. "
        "The user must confirm it; explain briefly why you need it.", {"command": S}, ["command"]),
]
FILE_TOOLS = {"list_files", "read_file", "write_file", "edit_file", "make_folder", "delete_file", "search_files",
              "workspace_note", "undo_change", "run_command"}
MUTATING = {"write_file", "edit_file", "make_folder", "delete_file", "undo_change", "run_command"}


def execute(name: str, args: dict, ask=None):
    try:
        if name == "undo_change":
            return undo()
        if name == "run_command":
            return run_command(args.get("command", ""), ask)
        fn = {"list_files": list_files, "read_file": read_file, "write_file": write_file, "edit_file": edit_file,
              "make_folder": make_folder, "delete_file": delete_file, "search_files": search_files,
              "workspace_note": workspace_note}[name]
        import inspect

        accepted = inspect.signature(fn).parameters
        return fn(**{k: v for k, v in (args or {}).items() if k in accepted})
    except WorkspaceError as exc:
        return {"error": str(exc)}
    except TypeError as exc:
        return {"error": f"bad arguments: {exc}"}
    except OSError as exc:
        return {"error": str(exc)}


def summary_json() -> str:
    return json.dumps({"name": active["name"], "description": active["description"]}, ensure_ascii=False)
