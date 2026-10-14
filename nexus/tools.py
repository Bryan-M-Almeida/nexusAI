"""Actions the assistant can execute (OpenAI-style function calling)."""
import functools
import inspect
import json
from datetime import datetime, timedelta

from . import integrations, knowledge, memory, profile
from .config import DATA_DIR, settings
from .db import db, now

REPORTS_DIR = DATA_DIR / "reports"


def _dt(value: str | None) -> str | None:
    """Validate and normalise an ISO date/datetime coming from the model."""
    if not value:
        return None
    value = str(value).strip().replace("Z", "")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Data inválida/invalid date '{value}'. Use ISO: YYYY-MM-DDTHH:MM")
    return dt.isoformat(timespec="minutes")


# ---------------------------------------------------------------- tasks
def add_task(title, due=None, priority="normal", notes=""):
    due = _dt(due)
    tid = db.execute(
        "INSERT INTO tasks(title, notes, due, priority, created) VALUES (?,?,?,?,?)",
        (title, notes or "", due, priority or "normal", now()),
    ).lastrowid
    db.log_action("tarefa", f"Criou tarefa #{tid}: {title}" + (f" (prazo {due})" if due else ""))
    return {"ok": True, "id": tid, "title": title, "due": due}


def list_tasks(status="pending"):
    where = {"pending": "WHERE done = 0", "done": "WHERE done = 1"}.get(status, "")
    return db.all(f"SELECT id, title, notes, due, priority, done FROM tasks {where} ORDER BY done, due IS NULL, due, id")


def complete_task(task_id):
    row = db.one("SELECT title FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return {"ok": False, "error": f"task {task_id} not found"}
    db.execute("UPDATE tasks SET done = 1, done_at = ? WHERE id = ?", (now(), task_id))
    db.log_action("tarefa", f"Concluiu tarefa #{task_id}: {row['title']}")
    return {"ok": True}


def delete_task(task_id):
    row = db.one("SELECT title FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return {"ok": False, "error": f"task {task_id} not found"}
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.log_action("tarefa", f"Removeu tarefa #{task_id}: {row['title']}")
    return {"ok": True}


# ---------------------------------------------------------------- schedule
def add_event(title, start, end=None, remind_minutes=10, notes=""):
    start, end = _dt(start), _dt(end)
    eid = db.execute(
        "INSERT INTO events(title, start, end, notes, remind_minutes, created) VALUES (?,?,?,?,?,?)",
        (title, start, end, notes or "", int(remind_minutes if remind_minutes is not None else 10), now()),
    ).lastrowid
    db.log_action("agenda", f"Agendou #{eid}: {title} em {start}")
    return {"ok": True, "id": eid, "title": title, "start": start}


def set_reminder(text, at):
    return add_event(text, at, remind_minutes=0, notes="reminder")


def list_events(start=None, end=None):
    start = _dt(start) or datetime.now().replace(hour=0, minute=0).isoformat(timespec="minutes")
    end = _dt(end) or (datetime.fromisoformat(start) + timedelta(days=7)).isoformat(timespec="minutes")
    return db.all(
        "SELECT id, title, start, end, notes, remind_minutes FROM events WHERE start >= ? AND start <= ? ORDER BY start",
        (start, end),
    )


def delete_event(event_id):
    row = db.one("SELECT title FROM events WHERE id = ?", (event_id,))
    if not row:
        return {"ok": False, "error": f"event {event_id} not found"}
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.log_action("agenda", f"Cancelou #{event_id}: {row['title']}")
    return {"ok": True}


# ---------------------------------------------------------------- notes & data
def save_note(title, content, tags=""):
    existing = db.one("SELECT id FROM notes WHERE lower(title) = lower(?)", (title,))
    if existing:
        db.execute("UPDATE notes SET content=?, tags=?, updated=? WHERE id=?", (content, tags or "", now(), existing["id"]))
        db.log_action("nota", f"Atualizou nota: {title}")
        return {"ok": True, "id": existing["id"], "updated": True}
    nid = db.execute(
        "INSERT INTO notes(title, content, tags, created, updated) VALUES (?,?,?,?,?)",
        (title, content, tags or "", now(), now()),
    ).lastrowid
    db.log_action("nota", f"Criou nota: {title}")
    return {"ok": True, "id": nid}


def search_notes(query=""):
    like = f"%{query}%"
    return db.all(
        "SELECT id, title, content, tags, updated FROM notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY updated DESC LIMIT 10",
        (like, like, like),
    )


def record_data(collection, data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {"value": data}
    collection = collection.strip().lower()
    rid = db.execute(
        "INSERT INTO records(collection, data, created) VALUES (?,?,?)",
        (collection, json.dumps(data, ensure_ascii=False), now()),
    ).lastrowid
    db.log_action("dados", f"Registrou em '{collection}': {json.dumps(data, ensure_ascii=False)[:80]}")
    return {"ok": True, "id": rid}


def query_data(collection, limit=50):
    rows = db.all(
        "SELECT id, data, created FROM records WHERE collection = ? ORDER BY id DESC LIMIT ?",
        (collection.strip().lower(), int(limit)),
    )
    return [{"id": r["id"], "created": r["created"], **json.loads(r["data"])} for r in rows]


def list_collections():
    return db.all("SELECT collection, COUNT(*) AS items, MAX(created) AS last FROM records GROUP BY collection")


def delete_record(record_id):
    db.execute("DELETE FROM records WHERE id = ?", (record_id,))
    db.log_action("dados", f"Removeu registro #{record_id}")
    return {"ok": True}


# ---------------------------------------------------------------- memory & knowledge
def remember(content, category="geral"):
    saved = memory.remember(content, category)
    return {"ok": True, "saved": bool(saved)}


def recall(query):
    return memory.recall(query) or memory.recent_memories(5)


def forget(memory_id):
    return {"ok": memory.forget(int(memory_id))}


def search_knowledge(query, category=None):
    hits = knowledge.search(query, limit=4, category=category)
    return [{"source": h["title"], "section": h["heading"], "text": h["content"]} for h in hits] or {
        "result": "nothing found / nada encontrado"
    }


def learn_knowledge(title, content, category="aprendido"):
    return {"ok": True, **knowledge.learn(title, content, category)}


def remind_next_session(topic):
    topic = str(topic).strip().rstrip("?.!")
    nid = db.execute("INSERT INTO session_notes(topic, created) VALUES (?, ?)", (topic, now())).lastrowid
    db.log_action("memória", f"Lembrar ao abrir: {topic}")
    return {"ok": True, "id": nid}


def conversation_control(action):
    # Executed by Assistant._control (it needs the speaker and the previous answer).
    return {"error": "handled by the assistant"}


def update_profile(field, value):
    profile.update_field(field, value)
    return {"ok": True}


def report_issue(description=""):
    """Save the current conversation (+ recent actions and settings) to a Markdown file the user can send to
    the developers. Works in temporary chats too: the file is only written because the user asked."""
    from . import __version__

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = REPORTS_DIR / f"nexus-report-{stamp}.md"
    lines = [f"# NEXUS report {stamp}", "", f"- version: {__version__}", f"- model: {settings['llm_model']}",
             f"- ai_mode: {settings['ai_mode']}", f"- language: {settings['language']}",
             f"- temporary chat: {memory.temporary}", "", "## Description", "", str(description or "-"), "",
             "## Conversation", ""]
    for m in memory.history(200):
        lines += [f"**{m['role']}** ({m.get('ts', '')[:16]}):", "", m["content"], ""]
    lines += ["## Recent actions", ""]
    lines += [f"- {a['ts'][:16]} [{a['kind']}] {a['summary']}" for a in memory.recent_actions(30)]
    path.write_text("\n".join(lines), encoding="utf-8")
    db.log_action("relatório", f"Conversa salva para relatar erro: {path.name}")
    return {"ok": True, "file": str(path)}


# ---------------------------------------------------------------- online integrations (v0.6)
def _online(fn):
    @functools.wraps(fn)  # keeps the real signature: execute() filters arguments with inspect.signature
    def wrapper(**kwargs):
        if not settings["integrations"]:
            return {"error": "online integrations are disabled in Settings"}
        return fn(**kwargs)
    return wrapper


get_weather = _online(integrations.get_weather)
get_news = _online(integrations.get_news)
convert_currency = _online(integrations.convert_currency)
wikipedia = _online(integrations.wikipedia)
sync_calendar = _online(integrations.sync_calendar)


def get_datetime():
    d = datetime.now()
    return {"now": d.isoformat(timespec="minutes"), "weekday": d.strftime("%A")}


# ---------------------------------------------------------------- schema
def _fn(name, desc, props=None, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props or {}, "required": list(required)},
        },
    }


S, I, O = {"type": "string"}, {"type": "integer"}, {"type": "object"}
ISO = {"type": "string", "description": "ISO datetime YYYY-MM-DDTHH:MM (local time)"}

SCHEMAS = [
    _fn("add_task", "Create a to-do task for the user.",
        {"title": S, "due": ISO, "priority": {"type": "string", "enum": ["low", "normal", "high"]}, "notes": S}, ["title"]),
    _fn("list_tasks", "List tasks.", {"status": {"type": "string", "enum": ["pending", "done", "all"]}}),
    _fn("complete_task", "Mark a task as done.", {"task_id": I}, ["task_id"]),
    _fn("delete_task", "Delete a task.", {"task_id": I}, ["task_id"]),
    _fn("add_event", "Add an appointment/event to the user's schedule (calendar).",
        {"title": S, "start": ISO, "end": ISO, "remind_minutes": {"type": "integer", "description": "minutes before start to alert"}, "notes": S},
        ["title", "start"]),
    _fn("set_reminder", "Set a reminder that alerts the user at a specific time.", {"text": S, "at": ISO}, ["text", "at"]),
    _fn("list_events", "List schedule events between two datetimes (default: next 7 days).", {"start": ISO, "end": ISO}),
    _fn("delete_event", "Cancel/delete an event.", {"event_id": I}, ["event_id"]),
    _fn("save_note", "Save or update a note (same title updates it).", {"title": S, "content": S, "tags": S}, ["title", "content"]),
    _fn("search_notes", "Search the user's notes.", {"query": S}),
    _fn("record_data", "Store a structured record in a named collection (e.g. expenses, workouts, readings, contacts).",
        {"collection": S, "data": {"type": "object", "description": "fields of the record, e.g. {\"amount\": 32.5, \"item\": \"lunch\"}"}},
        ["collection", "data"]),
    _fn("query_data", "Read records of a collection to answer questions or compute totals.", {"collection": S, "limit": I}, ["collection"]),
    _fn("list_collections", "List data collections the user has."),
    _fn("delete_record", "Delete a record by id.", {"record_id": I}, ["record_id"]),
    _fn("remember", "Save a durable fact about the user (preference, person, habit, decision).",
        {"content": S, "category": {"type": "string", "description": "e.g. preferencia, pessoa, saude, trabalho, rotina"}}, ["content"]),
    _fn("recall", "Search long-term memories about the user.", {"query": S}, ["query"]),
    _fn("forget", "Delete a memory by id when the user asks to forget it.", {"memory_id": I}, ["memory_id"]),
    _fn("search_knowledge", "Search the local knowledge base (first aid, philosophy, finance, programming, health, productivity and anything learned). Content exists in Portuguese, English and Spanish: use keywords in the user's language.",
        {"query": S, "category": S}, ["query"]),
    _fn("learn_knowledge", "Store new knowledge the user teaches or asks to learn. Same title updates it.",
        {"title": S, "content": S, "category": S}, ["title", "content"]),
    _fn("remind_next_session",
        "ONLY when the user explicitly asks to be reminded of something the next time they open/start NEXUS "
        "(e.g. 'next time I open, remind me to continue the app project'). NEXUS will greet them with it.",
        {"topic": {"type": "string", "description": "short noun phrase with article, in the user's language, "
                                                     "e.g. 'o projeto do app de finanças' / 'the finance app project'"}},
        ["topic"]),
    _fn("conversation_control",
        "Control your own speech when the user asks about the conversation itself: 'repeat' (say the last answer "
        "again), 'clearer' (user didn't understand -> explain again more clearly), 'pause', 'resume' (continue "
        "speaking), 'stop' (be quiet).",
        {"action": {"type": "string", "enum": ["repeat", "clearer", "pause", "resume", "stop"]}}, ["action"]),
    _fn("update_profile", "Update a field of the user's profile (name, profession, routine, interests, goals, language).",
        {"field": S, "value": S}, ["field", "value"]),
    _fn("report_issue",
        "Save this whole conversation to a report file when the user wants to report an error/bug/problem of "
        "NEXUS to the developers (e.g. 'salve essa conversa para relatar erros', 'report this bug').",
        {"description": {"type": "string", "description": "what went wrong, in the user's words"}}),
    _fn("get_datetime", "Get the current local date and time."),
    _fn("get_weather", "Current weather and forecast (internet). City defaults to the user's city.",
        {"city": S, "days": {"type": "integer", "description": "1-7"}}),
    _fn("get_news", "Latest news headlines (internet), optionally about a topic.", {"topic": S, "limit": I}),
    _fn("convert_currency", "Convert money between currencies with today's reference rate (internet). ISO codes.",
        {"amount": {"type": "number"}, "from_currency": S, "to_currency": S}, ["from_currency", "to_currency"]),
    _fn("wikipedia", "Look up a person, place or concept on Wikipedia (internet) when the local base has nothing.",
        {"query": S}, ["query"]),
    _fn("sync_calendar", "Import the user's calendar (ICS link from Settings) into the schedule now."),
]

REGISTRY = {s["function"]["name"]: globals()[s["function"]["name"]] for s in SCHEMAS}
# Tools that change data the UI shows -> UI panels refresh after them.
MUTATING = {"add_task", "complete_task", "delete_task", "add_event", "set_reminder", "delete_event",
            "save_note", "record_data", "delete_record", "remember", "forget", "learn_knowledge", "update_profile",
            "remind_next_session", "sync_calendar"}


def execute(name: str, args: dict):
    fn = REGISTRY.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    # Small models sometimes invent parameters (e.g. "status" on list_events): drop them.
    accepted = inspect.signature(fn).parameters
    args = {k: v for k, v in (args or {}).items() if k in accepted and v is not None}
    try:
        return fn(**args)
    except TypeError as exc:
        return {"error": f"bad arguments: {exc}"}
    except Exception as exc:
        return {"error": str(exc)}
