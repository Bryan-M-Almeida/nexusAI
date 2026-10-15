"""Long-term memory: facts about the user, conversation history and the action log."""
import re
from datetime import datetime, timedelta

from .db import db, now
from .knowledge import fts_query


def _norm(text: str) -> str:
    return " ".join(text.lower().strip(" .!").split())


_FILLER = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "e", "que", "um", "uma", "em", "no", "na", "com",
           "usuario", "usuário", "user", "the", "is", "of", "and", "el", "la", "los", "las", "y", "en", "es"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 2 and w not in _FILLER}


_NEGATION = re.compile(r"\b(não|nao|nunca|not|never|no|nunca|ya no|não mais)\b", re.IGNORECASE)


def similar(a: str, b: str, threshold: float = 0.8) -> bool:
    """Same idea in other words ("O usuário tem dois gatos" ~ "Tem dois gatos"). A negation on only one side
    ("gosta de café" vs "não gosta de café") is a correction, not a duplicate."""
    if bool(_NEGATION.search(a)) != bool(_NEGATION.search(b)):
        return False
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return _norm(a) == _norm(b)
    return len(wa & wb) / min(len(wa), len(wb)) >= threshold


# The user's message states something about themselves (not a question about the world).
_SELF = re.compile(r"\b(eu|meu|minha|meus|minhas|sou|tenho|gosto|prefiro|moro|trabalho|estudo|nasci|chamo|"
                   r"i|i'm|im|my|me|mine|yo|mi|mis|soy|tengo|prefiero|vivo|trabajo|estoy)\b", re.IGNORECASE)


def states_fact(user_text: str) -> bool:
    """Run automatic memory extraction only for self-statements; questions never become 'facts'."""
    text = user_text.strip()
    return bool(_SELF.search(text)) and not text.endswith("?")


def remember(content: str, category: str = "geral", source: str = "chat") -> dict | None:
    content = content.strip()
    if not content:
        return None
    for row in db.all("SELECT id, content FROM memories"):
        if similar(row["content"], content):  # already known, maybe worded differently
            return None
    mid = db.execute(
        "INSERT INTO memories(content, category, source, created) VALUES (?,?,?,?)",
        (content, category, source, now()),
    ).lastrowid
    db.log_action("memória", f"Memorizou: {content}")
    return {"id": mid, "content": content, "category": category}


def forget(memory_id: int) -> bool:
    row = db.one("SELECT content FROM memories WHERE id = ?", (memory_id,))
    if not row:
        return False
    db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    db.log_action("memória", f"Esqueceu: {row['content']}")
    return True


def recall(query: str, limit: int = 6) -> list[dict]:
    q = fts_query(query)
    if not q:
        return []
    return db.all(
        "SELECT m.id, m.content, m.category, m.created FROM memories_fts f "
        "JOIN memories m ON m.id = f.rowid WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT ?",
        (q, limit),
    )


def recent_memories(limit: int = 8) -> list[dict]:
    return db.all("SELECT id, content, category, created FROM memories ORDER BY id DESC LIMIT ?", (limit,))


def all_memories() -> list[dict]:
    return db.all("SELECT id, content, category, source, created FROM memories ORDER BY id DESC")


def recent_actions(limit: int = 10, since: str | None = None) -> list[dict]:
    if since:
        return db.all("SELECT ts, kind, summary FROM actions WHERE ts >= ? ORDER BY id DESC LIMIT ?", (since, limit))
    return db.all("SELECT ts, kind, summary FROM actions ORDER BY id DESC LIMIT ?", (limit,))


# Temporary conversation (v0.7): small talk that must not be saved. Messages live only in RAM and are discarded
# when the mode is turned off; automatic memory extraction is skipped while it is on.
temporary = False
_temp: list[dict] = []


def set_temporary(on: bool):
    global temporary
    temporary = bool(on)
    _temp.clear()


# Conversations (v0.9). Every message belongs to one. A new conversation starts when the app opens, when the
# user asks for one, or after 2 hours of silence; older ones can be reopened from the conversations panel.
# Only the open conversation is sent to the model: an ambiguous follow-up ("tell me the exact values") must
# never be answered with something from another conversation (NX-LLM-019).
CONVERSATION_IDLE = timedelta(hours=2)
_current: int | None = None  # None = the next message opens a new conversation


_workspace: int | None = None   # v0.11: id of the open workspace (its conversation is separate)
_saved_current: int | None = None


def enter_workspace(workspace_id: int, conversation_id: int | None) -> int:
    """Switch the history to the workspace's own conversation (created on first use). Returns its id."""
    global _current, _workspace, _saved_current
    if _workspace is None:
        _saved_current = _current
    _workspace = workspace_id
    if not conversation_id or not db.one("SELECT id FROM conversations WHERE id = ?", (conversation_id,)):
        ts = now()
        conversation_id = db.execute("INSERT INTO conversations(created, updated, workspace_id, title) VALUES (?,?,?,?)",
                                     (ts, ts, workspace_id, "workspace")).lastrowid
        db.execute("UPDATE workspaces SET conversation_id = ? WHERE id = ?", (conversation_id, workspace_id))
    _current = conversation_id
    return conversation_id


def leave_workspace():
    """Back to the normal conversation that was open before."""
    global _current, _workspace
    _workspace, _current = None, _saved_current


def in_workspace() -> bool:
    return _workspace is not None


def current_conversation() -> int | None:
    """Open conversation id, or None if the next message starts a new one (also after 2 h of silence)."""
    global _current
    if _current is not None and _workspace is None:  # a workspace keeps one continuous conversation
        row = db.one("SELECT updated FROM conversations WHERE id = ?", (_current,))
        if not row or datetime.now() - datetime.fromisoformat(row["updated"]) > CONVERSATION_IDLE:
            _current = None
    return _current


def new_conversation():
    """The next message starts a new conversation (button "New conversation")."""
    global _current
    _current = None


def open_conversation(conversation_id: int) -> bool:
    """Continue an older conversation: its messages become the model's history again."""
    global _current
    row = db.one("SELECT id FROM conversations WHERE id = ?", (int(conversation_id),))
    if not row:
        return False
    _current = row["id"]
    db.execute("UPDATE conversations SET updated = ? WHERE id = ?", (now(), _current))
    return True


def add_message(role: str, content: str):
    global _current
    if temporary:
        _temp.append({"role": role, "content": content, "ts": now()})
        return
    ts = now()
    if current_conversation() is None:
        # conversations that only got the opening greeting are noise: drop them before starting a new one
        normal = "SELECT id FROM conversations WHERE workspace_id IS NULL"
        db.execute(f"DELETE FROM messages WHERE conversation_id IN (SELECT conversation_id FROM messages "
                   f"WHERE conversation_id IN ({normal}) GROUP BY conversation_id HAVING SUM(role = 'user') = 0)")
        db.execute("DELETE FROM conversations WHERE workspace_id IS NULL AND id NOT IN "
                   "(SELECT DISTINCT conversation_id FROM messages WHERE conversation_id IS NOT NULL)")
        _current = db.execute("INSERT INTO conversations(created, updated) VALUES (?, ?)", (ts, ts)).lastrowid
    db.execute("INSERT INTO messages(role, content, ts, conversation_id) VALUES (?,?,?,?)", (role, content, ts, _current))
    db.execute("UPDATE conversations SET updated = ? WHERE id = ?", (ts, _current))
    if role == "user":
        conv = db.one("SELECT title FROM conversations WHERE id = ?", (_current,))
        if conv and not conv["title"]:  # provisional title; the assistant replaces it with a better one
            db.execute("UPDATE conversations SET title = ? WHERE id = ?", (_short(content), _current))


def _short(text: str, words: int = 8) -> str:
    return " ".join(text.split()[:words])[:60]


def session_start() -> str:
    """Start of the open conversation (recent actions older than this belong to other conversations)."""
    cid = current_conversation()
    row = db.one("SELECT created FROM conversations WHERE id = ?", (cid,)) if cid else None
    return row["created"] if row else now()


def history(turns: int) -> list[dict]:
    """Last `turns` exchanges of the open conversation (oldest first)."""
    if temporary:
        return list(_temp[-turns * 2:])
    cid = current_conversation()
    if cid is None:
        return []
    rows = db.all("SELECT role, content, ts FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
                  (cid, turns * 2))
    return list(reversed(rows))


def conversations(limit: int = 200) -> list[dict]:
    """Conversations with at least one user message, most recent first."""
    return db.all(
        "SELECT c.id, c.title, c.description, c.created, c.updated, COUNT(m.id) AS messages "
        "FROM conversations c JOIN messages m ON m.conversation_id = c.id WHERE c.workspace_id IS NULL "
        "GROUP BY c.id HAVING SUM(m.role = 'user') > 0 ORDER BY c.updated DESC LIMIT ?", (limit,))


def conversation_messages(conversation_id: int) -> list[dict]:
    return db.all("SELECT id, role, content, ts FROM messages WHERE conversation_id = ? ORDER BY id",
                  (int(conversation_id),))


def timeline(limit: int = 300, before_id: int | None = None) -> list[dict]:
    """Every message of every conversation in chronological order (the "All" view), newest page first."""
    rows = db.all(
        "SELECT m.id, m.role, m.content, m.ts, m.conversation_id, c.title FROM messages m "
        "LEFT JOIN conversations c ON c.id = m.conversation_id WHERE m.id < ? AND c.workspace_id IS NULL "
        "ORDER BY m.id DESC LIMIT ?",
        (before_id or 2 ** 62, limit))
    return list(reversed(rows))


def set_conversation_title(conversation_id: int, title: str, description: str = "", final: bool = False):
    db.execute("UPDATE conversations SET title = ?, description = ?, titled_at = CASE WHEN ? THEN -1 ELSE "
               "(SELECT COUNT(*) FROM messages WHERE conversation_id = ?) END WHERE id = ?",
               (title.strip()[:80], description.strip()[:240], final, conversation_id, conversation_id))


def delete_conversation(conversation_id: int):
    global _current
    db.execute("DELETE FROM messages WHERE conversation_id = ?", (int(conversation_id),))
    db.execute("DELETE FROM conversations WHERE id = ?", (int(conversation_id),))
    if _current == int(conversation_id):
        _current = None


def clear_history():
    global _current
    db.execute("DELETE FROM messages")
    db.execute("DELETE FROM conversations")
    _current = None
    db.log_action("sistema", "Histórico de conversa limpo")

