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


def add_message(role: str, content: str):
    db.execute("INSERT INTO messages(role, content, ts) VALUES (?,?,?)", (role, content, now()))


# A conversation "session" starts when the app opens; a long silence also starts a new one.
# Older conversations stay in the database but are not sent to the model: otherwise an ambiguous
# follow-up ("tell me the exact values") gets answered with something from hours ago (NX-LLM-019).
SESSION_START = now()
SESSION_IDLE = timedelta(hours=2)


def session_start() -> str:
    """Start of the current session: app start, or the end of the last 2-hour silence after it."""
    rows = db.all("SELECT ts FROM messages WHERE ts >= ? ORDER BY id DESC LIMIT 200", (SESSION_START,))
    start = SESSION_START
    for newer, older in zip(rows, rows[1:]):
        if datetime.fromisoformat(newer["ts"]) - datetime.fromisoformat(older["ts"]) > SESSION_IDLE:
            start = newer["ts"]
            break
    if rows and datetime.now() - datetime.fromisoformat(rows[0]["ts"]) > SESSION_IDLE:
        start = now()  # silent for 2 h: the next message opens a fresh session
    return start


def history(turns: int) -> list[dict]:
    """Last `turns` exchanges of the current session (oldest first)."""
    rows = db.all("SELECT role, content, ts FROM messages WHERE ts >= ? ORDER BY id DESC LIMIT ?",
                  (session_start(), turns * 2))
    return list(reversed(rows))


def clear_history():
    db.execute("DELETE FROM messages")
    db.log_action("sistema", "Histórico de conversa limpo")
