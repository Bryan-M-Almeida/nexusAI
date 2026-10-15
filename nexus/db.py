"""SQLite storage shared by every module (one connection guarded by a lock)."""
import json
import sqlite3
import threading
from datetime import datetime

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'geral',
    source TEXT NOT NULL DEFAULT 'chat',
    created TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, category, content='memories', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, category) VALUES (new.id, new.content, new.category);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, category) VALUES ('delete', old.id, old.content, old.category);
END;
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    due TEXT,
    priority TEXT NOT NULL DEFAULT 'normal',
    done INTEGER NOT NULL DEFAULT 0,
    reminded INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL,
    done_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT,
    notes TEXT NOT NULL DEFAULT '',
    remind_minutes INTEGER NOT NULL DEFAULT 10,
    reminded INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    collection TEXT NOT NULL,
    data TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_collection ON records(collection);
CREATE TABLE IF NOT EXISTS kb_docs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL UNIQUE,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_notes (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    created TEXT NOT NULL,
    delivered TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- ids of deleted conversations are never reused
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    titled_at INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    folder TEXT NOT NULL UNIQUE,
    conversation_id INTEGER,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    op TEXT NOT NULL,
    path TEXT NOT NULL,
    backup TEXT NOT NULL DEFAULT '',
    undone INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS skills (
    skill TEXT PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders_sent (
    kind TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    lead INTEGER NOT NULL,
    ts TEXT NOT NULL,
    PRIMARY KEY (kind, item_id, lead)
);
CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks USING fts5(
    heading, content, category UNINDEXED, doc_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DB:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self._migrate()

    def _migrate(self):
        """Columns added after v0.1 (databases created by older versions get them on start)."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(events)")}
        if "external_id" not in cols:  # v0.6: events imported from a calendar feed (ICS UID)
            self.conn.execute("ALTER TABLE events ADD COLUMN external_id TEXT")
            self.conn.commit()
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(messages)")}
        if "conversation_id" not in cols:  # v0.9: messages belong to conversations
            self.conn.execute("ALTER TABLE messages ADD COLUMN conversation_id INTEGER")
            self.conn.execute("CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id)")
            self._split_old_messages()
            self.conn.commit()
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(conversations)")}
        if "workspace_id" not in cols:  # v0.11: a workspace's conversation never shows up among normal ones
            self.conn.execute("ALTER TABLE conversations ADD COLUMN workspace_id INTEGER")
            self.conn.commit()

    def _split_old_messages(self, gap_hours: float = 2):
        """Group messages saved before v0.9 into conversations: a silence of 2 h starts a new one (the same rule
        the old 'session' used). Titles come from the first user message."""
        rows = self.conn.execute("SELECT id, role, content, ts FROM messages ORDER BY id").fetchall()
        groups, last = [], None
        for r in rows:
            ts = datetime.fromisoformat(r["ts"])
            if last is None or (ts - last).total_seconds() > gap_hours * 3600:
                groups.append([])
            groups[-1].append(r)
            last = ts
        for g in groups:
            first_user = next((r["content"] for r in g if r["role"] == "user"), "")
            title = " ".join(first_user.split()[:8])[:60]
            cid = self.conn.execute(
                "INSERT INTO conversations(title, created, updated) VALUES (?,?,?)",
                (title, g[0]["ts"], g[-1]["ts"])).lastrowid
            self.conn.execute("UPDATE messages SET conversation_id = ? WHERE id BETWEEN ? AND ?",
                              (cid, g[0]["id"], g[-1]["id"]))

    def execute(self, sql, params=()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def all(self, sql, params=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def log_action(self, kind: str, summary: str):
        self.execute("INSERT INTO actions(ts, kind, summary) VALUES (?,?,?)", (now(), kind, summary))

    # -- small key/value state (e.g. whether NEXUS already introduced itself) ----
    def get_state(self, key: str, default=None):
        row = self.one("SELECT value FROM state WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_state(self, key: str, value: str):
        self.execute("INSERT INTO state(key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    # -- profile ---------------------------------------------------------
    def get_profile(self) -> dict | None:
        row = self.one("SELECT data FROM profile WHERE id = 1")
        return json.loads(row["data"]) if row else None

    def set_profile(self, data: dict):
        self.execute(
            "INSERT INTO profile(id, data, updated) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated = excluded.updated",
            (json.dumps(data, ensure_ascii=False), now()),
        )


db = DB()
