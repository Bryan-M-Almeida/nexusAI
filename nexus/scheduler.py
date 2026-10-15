"""Real-time loop (while the app is open): reminders with several lead times, the daily briefing and the
calendar sync. Each reminder is sent once per lead (table reminders_sent)."""
import threading
import time
from datetime import datetime, timedelta

from .config import settings
from .db import db, now
from .i18n import t

INTERVAL = 15
STALE = timedelta(hours=1)  # a reminder whose moment passed more than this ago (app was closed) is dropped


def leads() -> list[int]:
    """Minutes before the item, largest first; 0 (at the time) is always included."""
    out = {0}
    for part in str(settings.get("reminder_leads", "")).replace(";", ",").split(","):
        try:
            if 0 <= int(part) <= 7 * 24 * 60:
                out.add(int(part))
        except ValueError:
            pass
    return sorted(out, reverse=True)


def lead_text(minutes: int) -> str:
    if minutes % 1440 == 0:
        return t("lead_days", n=minutes // 1440) if minutes > 1440 else t("lead_day")
    if minutes % 60 == 0:
        return t("lead_hours", n=minutes // 60) if minutes > 60 else t("lead_hour")
    return t("lead_minutes", n=minutes)


def _due_lead(kind: str, item_id: int, at: datetime, item_leads: list[int], moment: datetime, created: datetime):
    """The lead to fire now for one item, or None. If the app opened late and several leads already passed,
    only the closest one is announced (the others are marked as sent)."""
    # leads already past when the item was created ("in 1 hour" for something 30 min away) are skipped
    passed = [lead for lead in item_leads if at - timedelta(minutes=lead) <= moment
              and (lead == 0 or at - timedelta(minutes=lead) > created)]
    if not passed:
        return None
    sent = {r["lead"] for r in db.all("SELECT lead FROM reminders_sent WHERE kind = ? AND item_id = ?", (kind, item_id))}
    fresh = [lead for lead in passed if lead not in sent]
    if not fresh:
        return None
    for lead in fresh:
        db.execute("INSERT OR IGNORE INTO reminders_sent(kind, item_id, lead, ts) VALUES (?,?,?,?)",
                   (kind, item_id, lead, now()))
    lead = min(fresh)
    if at - timedelta(minutes=lead) < moment - STALE:
        return None
    return lead


def _message(kind: str, title: str, at: datetime, lead: int, plain_reminder: bool, moment: datetime) -> str:
    if plain_reminder or lead == 0:
        return t("reminder_now", title=title) if kind == "event" else t("task_due", title=title)
    left = max(1, round((at - moment).total_seconds() / 60))  # the real time left (the app may have opened late)
    key = "reminder_in" if kind == "event" else "task_in"
    return t(key, title=title, when=lead_text(left), time=at.strftime("%H:%M"))


def _check(alert):
    moment = datetime.now()
    oldest = (moment - STALE - timedelta(days=7)).isoformat(timespec="minutes")
    for e in db.all("SELECT * FROM events WHERE start >= ?", (oldest,)):
        at = datetime.fromisoformat(e["start"])
        plain = e["notes"] == "reminder"  # set_reminder ("remind me to drink water at 3"): only at the time
        item_leads = [0] if plain else sorted(set(leads()) | {int(e["remind_minutes"] or 0)}, reverse=True)
        lead = _due_lead("event", e["id"], at, item_leads, moment, datetime.fromisoformat(e["created"]))
        if lead is not None:
            db.execute("UPDATE events SET reminded = 1 WHERE id = ? AND ? = 0", (e["id"], lead))
            alert({"kind": "event", "id": e["id"], "title": e["title"], "start": e["start"], "lead": lead,
                   "text": _message("event", e["title"], at, lead, plain, moment)})
    for task in db.all("SELECT * FROM tasks WHERE done = 0 AND due IS NOT NULL AND due >= ?", (oldest,)):
        at = datetime.fromisoformat(task["due"])
        lead = _due_lead("task", task["id"], at, leads(), moment, datetime.fromisoformat(task["created"]))
        if lead is not None:
            db.execute("UPDATE tasks SET reminded = 1 WHERE id = ? AND ? = 0", (task["id"], lead))
            alert({"kind": "task", "id": task["id"], "title": task["title"], "lead": lead,
                   "text": _message("task", task["title"], at, lead, False, moment)})
    _briefing(alert, moment)


def briefing_text() -> str:
    """Deterministic summary of today (no AI): agenda + pending tasks."""
    from . import tools

    today = datetime.now().date().isoformat()
    events = [e for e in tools.list_events(f"{today}T00:00", f"{today}T23:59")]
    tasks = tools.list_tasks("pending")
    prof = db.get_profile() or {}
    name = (prof.get("name") or "").split(" ")[0]
    parts = [t("briefing_hello", name=name).replace(", .", ".")]  # no profile yet: "Bom dia."
    if events:
        parts.append(t("briefing_events", n=len(events), items="; ".join(
            f"{e['start'][11:16]} {e['title']}" for e in events[:6])))
    else:
        parts.append(t("briefing_no_events"))
    parts.append(t("briefing_tasks", n=len(tasks)) if tasks else t("briefing_no_tasks"))
    return " ".join(parts)


def _briefing(alert, moment: datetime):
    spec = str(settings.get("daily_briefing", "")).strip()
    if not spec:
        return
    try:
        at = datetime.combine(moment.date(), datetime.strptime(spec, "%H:%M").time())
    except ValueError:
        return
    today = moment.date().isoformat()
    if at <= moment < at + timedelta(hours=3) and db.get_state("briefing_date") != today:
        db.set_state("briefing_date", today)
        alert({"kind": "briefing", "title": t("briefing_title"), "text": briefing_text()})


def start(alert):
    from . import integrations

    def loop():
        while True:
            try:
                from . import netprobe

                online = settings["integrations"] and netprobe.effective() != "offline"
                if online and integrations.calendar_due():  # ICS calendar feed, every 30 min
                    integrations.sync_calendar()
                _check(alert)
            except Exception as exc:
                db.log_action("erro", f"Agendador: {exc}")
                from .logs import log

                log.exception("scheduler")
            time.sleep(INTERVAL)

    threading.Thread(target=loop, daemon=True, name="scheduler").start()
