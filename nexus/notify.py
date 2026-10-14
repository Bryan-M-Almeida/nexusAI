"""Notifications (v0.10): stored in a notification center, shown in the app, optionally as a Windows toast and
spoken aloud. Quiet hours keep them silent (no voice, no toast) but still listed."""
import subprocess
import sys
from datetime import datetime
from xml.sax.saxutils import escape

from .config import settings
from .db import db, now

# Windows only shows toasts for registered app ids; PowerShell's is always registered, so NEXUS borrows it
# until the installer (final prototype) registers its own.
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
_TOAST_PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{title}</text><text>{body}</text></binding></visual><audio silent="true"/></toast>')
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app}').Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""


def in_quiet_hours(at: datetime | None = None) -> bool:
    """settings["quiet_hours"] like "22:00-07:00" (may cross midnight); empty = never quiet."""
    spec = str(settings.get("quiet_hours", "")).strip()
    if "-" not in spec:
        return False
    try:
        start, end = (datetime.strptime(x.strip(), "%H:%M").time() for x in spec.split("-", 1))
    except ValueError:
        return False
    t = (at or datetime.now()).time()
    return start <= t < end if start <= end else (t >= start or t < end)


def toast(title: str, body: str):
    """Windows notification, fire-and-forget (~0.3 s in a hidden PowerShell; never blocks the app)."""
    if sys.platform != "win32":
        return
    xml_safe = lambda s: escape(str(s)).replace("'", "''")  # noqa: E731  (XML + PowerShell single quotes)
    script = _TOAST_PS.replace("{title}", xml_safe(title)).replace("{body}", xml_safe(body)).replace("{app}", _APP_ID)
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def add(kind: str, title: str, body: str = "") -> dict:
    nid = db.execute("INSERT INTO notifications(ts, kind, title, body) VALUES (?,?,?,?)",
                     (now(), kind, title, body)).lastrowid
    db.execute("DELETE FROM notifications WHERE id <= ?", (nid - 500,))  # keep the last 500
    return {"id": nid, "ts": now(), "kind": kind, "title": title, "body": body, "read": 0}


def listing(limit: int = 100) -> dict:
    return {"items": db.all("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)),
            "unread": db.one("SELECT COUNT(*) n FROM notifications WHERE read = 0")["n"]}


def mark_read():
    db.execute("UPDATE notifications SET read = 1 WHERE read = 0")


def clear():
    db.execute("DELETE FROM notifications")
