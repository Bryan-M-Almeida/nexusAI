"""Downloads monitor (v0.19.0): everything NEXUS downloads (AI models, the voice model) in one place, like a
terminal - progress, speed, time left and a "stalled" warning when nothing arrives for a while, so the user can tell a
slow download from a frozen one. The interface polls state(); entries live only while NEXUS is open."""
import itertools
import threading
import time
from collections import deque

STALL_SECONDS = 20  # no new bytes for this long = "stalled" (the download may still recover)
_lock = threading.Lock()
_ids = itertools.count(1)
ITEMS: dict[int, dict] = {}
LOG: deque = deque(maxlen=300)


def _log(item: dict, text: str, level: str = "info"):
    LOG.append({"ts": time.strftime("%H:%M:%S"), "id": item["id"], "name": item["name"], "text": text, "level": level})


def start(kind: str, name: str, total: int = 0) -> int:
    """A new download ("model" / "voice"); returns its id for update() and finish()."""
    with _lock:
        did = next(_ids)
        now = time.time()
        ITEMS[did] = {"id": did, "kind": kind, "name": name, "total": int(total or 0), "done": 0, "started": now,
                      "progress_at": now, "status": "running", "error": "", "speed": 0.0, "_logged": -1, "_last": (now, 0)}
        _log(ITEMS[did], f"start {kind} {name}")
        return did


def update(did: int, done: int, total: int | None = None, note: str = ""):
    with _lock:
        item = ITEMS.get(did)
        if not item or item["status"] != "running":
            return
        now = time.time()
        if total:
            item["total"] = int(total)
        if done > item["done"]:
            t0, d0 = item["_last"]
            if now - t0 >= 1.0:  # speed over ~1 s windows, smoothed
                inst = (done - d0) / (now - t0)
                item["speed"] = inst if not item["speed"] else 0.6 * item["speed"] + 0.4 * inst
                item["_last"] = (now, done)
            item["done"], item["progress_at"] = int(done), now
        pct = int(100 * item["done"] / item["total"]) if item["total"] else 0
        if pct // 10 != item["_logged"] or note:  # one line every 10% (or when something happens)
            item["_logged"] = pct // 10
            _log(item, note or f"{pct:3d}%  {_mb(item['done'])}/{_mb(item['total'])}  {_mb(item['speed'])}/s")


def finish(did: int, ok: bool = True, error: str = ""):
    with _lock:
        item = ITEMS.get(did)
        if not item:
            return
        item["status"] = "done" if ok else "error"
        item["error"] = error[:200]
        if ok and item["total"]:
            item["done"] = item["total"]
        secs = time.time() - item["started"]
        _log(item, f"done in {secs:.0f} s" if ok else f"failed: {error[:120]}", "ok" if ok else "error")


def _mb(n: float) -> str:
    return f"{n / 2 ** 30:.2f} GB" if n >= 2 ** 30 else f"{n / 2 ** 20:.1f} MB"


def state() -> dict:
    now = time.time()
    with _lock:
        items = []
        for it in sorted(ITEMS.values(), key=lambda x: -x["id"])[:20]:
            pub = {k: v for k, v in it.items() if not k.startswith("_")}
            left = (it["total"] - it["done"]) / it["speed"] if it["speed"] and it["total"] else None
            pub.update(pct=round(100 * it["done"] / it["total"], 1) if it["total"] else None, eta_s=round(left) if left else None,
                       stalled=it["status"] == "running" and now - it["progress_at"] > STALL_SECONDS,
                       idle_s=round(now - it["progress_at"]))
            items.append(pub)
        return {"items": items, "log": list(LOG)[-120:], "active": sum(i["status"] == "running" for i in ITEMS.values())}
