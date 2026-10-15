"""Log file (v0.13): logs/nexus.log (1 MB x 3 files). Errors that used to vanish in a background thread now leave a
trace, and "report an error" attaches the end of the log."""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from .config import LOG_DIR

log = logging.getLogger("nexus")


def setup():
    if log.handlers:
        return log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / "nexus.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    def on_error(exc_type, exc, tb):
        log.error("unhandled exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = on_error
    threading.excepthook = lambda args: log.error(f"unhandled exception in {args.thread.name if args.thread else '?'}",
                                                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    return log


def tail(lines: int = 80) -> str:
    f = LOG_DIR / "nexus.log"
    if not f.exists():
        return ""
    return "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
