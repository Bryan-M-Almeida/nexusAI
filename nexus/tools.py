"""Actions the assistant can execute (OpenAI-style function calling)."""
import functools
import inspect
import json
import time
from datetime import datetime, timedelta

from . import connectors, integrations, knowledge, memory, profile
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
    from .logs import tail

    log_tail = tail(80)
    if log_tail:
        lines += ["", "## Log (end of logs/nexus.log)", "", "```", log_tail, "```"]
    path.write_text("\n".join(lines), encoding="utf-8")
    db.log_action("relatório", f"Conversa salva para relatar erro: {path.name}")
    return {"ok": True, "file": str(path)}


# ---------------------------------------------------------------- library and browser (v0.15)
def list_books():
    from . import library

    return {"books": [{"title": b["title"], "progress": f"{round(b['progress'] * 100)}%"} for b in library.listing()]}


def read_book(title, from_start=False):
    """Start reading a library book aloud (podcast mode) from where the user stopped."""
    from . import library

    book = library.find(title)
    if not book:
        return {"error": f"no book matching '{title}' in the library", "books": list_books()["books"]}
    if library.player is None:
        return {"error": "the voice is not available"}
    library.player(book["id"], 0 if from_start else book["position"])
    return {"ok": True, "reading": book["title"], "from": "start" if from_start else f"{round(book['position'] / max(book['chars'], 1) * 100)}%"}


def open_url(url):
    from . import browser

    return browser.open_url(url)


def web_search(query):
    from . import browser

    return browser.web_search(query)


def _play_music_browser(query, service="youtube"):
    from . import browser

    return browser.music_search(query, service)


def play_music(query, service=""):
    service = (service or settings.get("music_player", "youtube")).lower()
    if service == "limusic":
        from . import apps, media

        app = apps.find("limusic")
        if not app:
            return {"error": "LiMusic is not installed (https://simohypers.github.io/limusic/)"}
        apps.launch(app)
        return {"ok": True, "opened": "LiMusic", "note": "LiMusic has no search link: it was opened; tell the user to "
                "search the song there (Ctrl+K). Play/pause/next work by voice.", "query": query,
                "media": media.now_playing().get("current")}
    return _play_music_browser(query, service if service in ("youtube", "youtube music", "spotify") else "youtube")


# v0.16.5: the AI opens the interface for the user ("quero mudar a cor do aro" -> Settings > Interface).
ui_hook = None  # set by the app; receives {"target", "section", "say"}
UI_BETA = {"library": "library", "workspace": "workspace", "skills": "skills", "map": "map"}


PANEL_TABS = ("memory", "knowledge", "data", "learned", "log")


def open_interface(target, section=None):
    from . import features

    if ui_hook is None:
        return {"error": "no interface"}
    if UI_BETA.get(target) and not features.enabled(UI_BETA[target]):
        return {"error": f"'{target}' is a beta feature that is off; the user can enable it in Settings > Beta"}
    if target == "panel" and section not in PANEL_TABS:
        section = None
    ui_hook({"target": target, "section": section if target in ("settings", "panel") else None, "say": ""})
    return {"opened": target, "section": section} if target != "close" else {"closed": True}


# ---------------------------------------------------------------- online integrations (v0.6)
# v0.18.0: every integration goes through the hub (nexus/connectors.py): one cache (kept on disk), the on/off switch of
# each integration, offline copies and the status shown in Settings > Integrations. Errors are never cached.
INTEGRATION_TOOLS = {"get_weather": "weather", "get_news": "news", "convert_currency": "currency", "wikipedia": "wikipedia",
                     "sync_calendar": "calendar"}


def integration_allowed(name: str) -> bool:
    cid = INTEGRATION_TOOLS.get(name)
    return cid is None or connectors.enabled(cid)


def get_weather(city="", days=3):
    city = city or settings["home_city"]
    if not city and connectors.online_allowed():
        return {"error": "no city: ask the user which city (it can be saved in Settings > Integrations)"}
    return connectors.call("weather", {"city": city, "days": max(1, min(int(days or 3), 7))})


def get_news(topic="", limit=5):
    return connectors.call("news", {"topic": topic or "", "limit": int(limit or 5)})


def convert_currency(amount=1, from_currency="USD", to_currency="BRL"):
    return connectors.call("currency", {"amount": float(amount or 1), "from_currency": str(from_currency).upper(),
                                        "to_currency": str(to_currency).upper()})


def wikipedia(query):
    return connectors.call("wikipedia", {"query": query})


def sync_calendar(days=30):
    return connectors.call("calendar", {"days": int(days or 30)})


def lookup(service, query):
    return connectors.lookup(service, query)


# ---------------------------------------------------------------- apps and media (v0.18.0, beta)
app_hook = None  # set by the app: app_hook(app) after a game opens -> NEXUS suspends itself
prefs_hook = None  # set by the app: prefs_hook(changed settings) -> the interface applies them (v0.18.5)


def set_preference(name, value):
    from . import prefs

    return prefs.set_preference(name, value)


def open_app_reply(app: dict, code: str) -> tuple[str, str, dict]:
    """Opens the app; (reply, tool name, args) for the assistant's instant path."""
    from . import apps, i18n

    result = apps.launch(app)
    if not result["ok"]:
        return i18n.STRINGS[code]["app_failed"].format(name=app["name"]), "open_app", result
    suspend = result["kind"] == "game" and settings.get("apps_suspend", "games") == "games" and app_hook is not None
    if suspend:
        app_hook(app)
    key = "app_game" if suspend else "app_opened"
    return i18n.STRINGS[code][key].format(name=app["name"]), "open_app", result


def open_app(name):
    from . import apps, i18n

    app = apps.find(name)
    if not app:
        return {"error": f"no installed app called '{name}'"}
    reply, _, result = open_app_reply(app, i18n.lang())
    return {**result, "said": reply}


def media_control(action, level=None):
    from . import media

    return media.control(action, level)


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
ISO = {"type": "string", "description": "local YYYY-MM-DDTHH:MM"}

SCHEMAS = [
    _fn("add_task", "Create a to-do task for the user.",
        {"title": S, "due": ISO, "priority": {"type": "string", "enum": ["low", "normal", "high"]}, "notes": S}, ["title"]),
    _fn("list_tasks", "List tasks.", {"status": {"type": "string", "enum": ["pending", "done", "all"]}}),
    _fn("complete_task", "Mark a task as done.", {"task_id": I}, ["task_id"]),
    _fn("delete_task", "Delete a task.", {"task_id": I}, ["task_id"]),
    _fn("add_event", "Add an appointment/event to the schedule.",
        {"title": S, "start": ISO, "end": ISO, "remind_minutes": I, "notes": S},
        ["title", "start"]),
    _fn("set_reminder", "Alert the user at a specific time.", {"text": S, "at": ISO}, ["text", "at"]),
    _fn("list_events", "List schedule events (default: next 7 days).", {"start": ISO, "end": ISO}),
    _fn("delete_event", "Cancel/delete an event.", {"event_id": I}, ["event_id"]),
    _fn("save_note", "Save or update a note (same title updates it).", {"title": S, "content": S, "tags": S}, ["title", "content"]),
    _fn("search_notes", "Search the user's notes.", {"query": S}),
    _fn("record_data", "Store a record in a named collection (expenses, workouts, readings...). data e.g. {\"amount\": 32.5, \"item\": \"lunch\"}.",
        {"collection": S, "data": O},
        ["collection", "data"]),
    _fn("query_data", "Read records of a collection to answer questions or compute totals.", {"collection": S, "limit": I}, ["collection"]),
    _fn("list_collections", "List data collections the user has."),
    _fn("delete_record", "Delete a record by id.", {"record_id": I}, ["record_id"]),
    _fn("remember", "Save a durable fact about the user (preference, person, habit, decision). category e.g. preferencia, "
        "pessoa, saude, trabalho, rotina.", {"content": S, "category": S}, ["content"]),
    _fn("recall", "Search long-term memories about the user.", {"query": S}, ["query"]),
    _fn("forget", "Delete a memory by id when the user asks to forget it.", {"memory_id": I}, ["memory_id"]),
    _fn("search_knowledge", "Search the local knowledge base (first aid, philosophy, finance, programming, health, "
        "productivity, anything learned). Keywords in the user's language.",
        {"query": S, "category": S}, ["query"]),
    _fn("learn_knowledge", "Store new knowledge the user teaches or asks to learn. Same title updates it.",
        {"title": S, "content": S, "category": S}, ["title", "content"]),
    _fn("remind_next_session", "ONLY when the user asks to be reminded of something the next time they open NEXUS. "
        "topic: short noun phrase with article in the user's language ('o projeto do app').", {"topic": S}, ["topic"]),
    _fn("conversation_control", "Your own speech: repeat the last answer, clearer (explain it again more simply), "
        "pause, resume, stop.",
        {"action": {"type": "string", "enum": ["repeat", "clearer", "pause", "resume", "stop"]}}, ["action"]),
    _fn("update_profile", "Update a field of the user's profile (name, profession, routine, interests, goals, language).",
        {"field": S, "value": S}, ["field", "value"]),
    _fn("report_issue", "Save this conversation to a report file when the user wants to report a NEXUS bug.",
        {"description": S}),
    _fn("list_books", "List the books in the user's library with their reading progress."),
    _fn("read_book", "Read a library book aloud (podcast mode), continuing where the user stopped.",
        {"title": S, "from_start": {"type": "boolean"}}, ["title"]),
    _fn("open_url", "Open a web page in the user's default browser.", {"url": S}, ["url"]),
    _fn("web_search", "Open a Google search in the user's browser (when they want to see results themselves).",
        {"query": S}, ["query"]),
    _fn("play_music", "Play a song/artist/video: opens the first YouTube result. service only when the user names "
        "another one.",
        {"query": S, "service": {"type": "string", "enum": ["youtube", "spotify", "limusic"]}}, ["query"]),
    _fn("open_interface", "Open (or close) part of the NEXUS interface for the user to SEE: settings with a section, "
        "panel with a tab, menus. To CHANGE colour, theme, size or voice use set_preference.",
        {"target": {"type": "string", "enum": ["settings", "panel", "conversations", "notifications", "library",
                                               "workspace", "skills", "map", "guide", "tutorial", "close"]},
         "section": {"type": "string", "enum": ["general", "ai", "memory", "voice", "mic", "listen", "ui", "custom", "keys",
                                                "integ", "apps", "notif", "amd", "perf", "data", "legal", "beta",
                                                "knowledge", "learned", "log"]}}, ["target"]),
    _fn("set_preference", "Change NEXUS's own look or voice now. name: theme (nexus|amd|emerald|violet|amber|graphite|"
        "ice), color_ring|color_core|color_bg (#rrggbb or colour name), ring_scale 60-140, ring_speed slow|normal|fast, "
        "exchange_size 12-24, bg_style glow|solid|grid, cursor_style, voice_gender male|female, voice_effect, tts_speed "
        "-5..10, tts_volume 0-100, show_hud/reduce_motion/ring_wander/show_exchange on|off.",
        {"name": S, "value": S}, ["name", "value"]),
    _fn("get_datetime", "Get the current local date and time."),
    _fn("get_weather", "Current weather and forecast (internet). City defaults to the user's city.",
        {"city": S, "days": {"type": "integer", "description": "1-7"}}),
    _fn("get_news", "Latest news headlines (internet), optionally about a topic.", {"topic": S, "limit": I}),
    _fn("convert_currency", "Convert money between currencies with today's reference rate (internet). ISO codes.",
        {"amount": {"type": "number"}, "from_currency": S, "to_currency": S}, ["from_currency", "to_currency"]),
    _fn("wikipedia", "Look up a person, place or concept on Wikipedia (internet) when the local base has nothing.",
        {"query": S}, ["query"]),
    _fn("sync_calendar", "Import the user's calendar (ICS link from Settings) into the schedule now."),
    _fn("lookup", "Live online data: crypto prices, time in another city (clock), translation, holidays, air "
        "quality/UV. query in natural language ('bitcoin in BRL', 'Tokyo', 'translate good night to Spanish').",
        {"service": {"type": "string", "enum": ["crypto", "clock", "translate", "holidays", "air"]}, "query": S},
        ["service", "query"]),
    _fn("open_app", "Open an app installed on the user's PC by name (Discord, VS Code, Spotify, a game...).",
        {"name": S}, ["name"]),
    _fn("media_control", "Control the music/video playing on the PC, or the system volume.",
        {"action": {"type": "string", "enum": ["play", "pause", "next", "previous", "volume", "volume_up", "volume_down",
                                               "mute", "unmute", "now_playing"]},
         "level": I}, ["action"]),
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
    from . import features

    if not features.tool_allowed(name):  # beta feature switched off (Settings > Beta)
        return {"error": f"'{name}' is a beta feature that is turned off; the user can enable it in Settings > Beta"}
    # Small models sometimes invent parameters (e.g. "status" on list_events): drop them.
    accepted = inspect.signature(fn).parameters
    args = {k: v for k, v in (args or {}).items() if k in accepted and v is not None}
    try:
        return fn(**args)
    except TypeError as exc:
        return {"error": f"bad arguments: {exc}"}
    except Exception as exc:
        return {"error": str(exc)}
