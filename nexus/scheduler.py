"""Real-time loop: fires reminders for events and due tasks."""
import threading
import time
from datetime import datetime, timedelta

from .db import db
from .i18n import t

INTERVAL = 15


def _check(alert):
    now = datetime.now()
    iso_now = now.isoformat(timespec="minutes")
    stale = (now - timedelta(hours=1)).isoformat(timespec="minutes")
    # Anything that should have fired more than an hour ago (app was closed) is skipped silently.
    db.execute("UPDATE events SET reminded = 1 WHERE reminded = 0 AND start < ?", (stale,))
    for e in db.all("SELECT * FROM events WHERE reminded = 0"):
        fire_at = datetime.fromisoformat(e["start"]) - timedelta(minutes=e["remind_minutes"])
        if fire_at <= now:
            db.execute("UPDATE events SET reminded = 1 WHERE id = ?", (e["id"],))
            alert({"kind": "event", "id": e["id"], "title": e["title"], "start": e["start"],
                   "text": t("event_soon", title=e["title"], time=e["start"][11:16])})
    for task in db.all("SELECT * FROM tasks WHERE done = 0 AND reminded = 0 AND due IS NOT NULL AND due <= ?", (iso_now,)):
        db.execute("UPDATE tasks SET reminded = 1 WHERE id = ?", (task["id"],))
        if task["due"] >= stale:
            alert({"kind": "task", "id": task["id"], "title": task["title"], "text": t("task_due", title=task["title"])})


def start(alert):
    def loop():
        while True:
            try:
                _check(alert)
            except Exception as exc:
                db.log_action("erro", f"Agendador: {exc}")
            time.sleep(INTERVAL)

    threading.Thread(target=loop, daemon=True, name="scheduler").start()
