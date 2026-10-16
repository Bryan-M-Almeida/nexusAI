"""Automatic connection mode (v0.15). In "auto", NEXUS measures the internet every few minutes (a tiny request for the
latency, ~250 KB for the speed) and behaves as:
  no internet         -> offline  (nothing leaves the PC)
  slow (> 1.2 s or < 1.5 Mbit/s) -> hybrid (local AI; online lookups only when needed, short waits)
  fast                -> online   (online lookups first for current/factual questions; still local AI unless an API
                                   is chosen)
The other modes (offline / hybrid / online) are fixed choices made in Settings."""
import threading
import time

import httpx

from .config import settings

PROBE_EVERY = 300        # seconds between measurements
SLOW_LATENCY_MS = 1200
SLOW_MBPS = 1.5
state = {"quality": None, "latency_ms": None, "mbps": None, "checked": 0.0}  # quality: offline | slow | fast
_listeners = []
_lock = threading.Lock()


def measure() -> dict:
    """One measurement (~0.3-2 s on a normal connection)."""
    latency = mbps = None
    try:
        t0 = time.perf_counter()
        httpx.get("https://www.google.com/generate_204", timeout=3)
        latency = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        r = httpx.get("https://speed.cloudflare.com/__down", params={"bytes": 250_000}, timeout=6)
        mbps = len(r.content) * 8 / 1e6 / max(time.perf_counter() - t0, 1e-3)
    except httpx.HTTPError:
        pass
    if latency is None:
        quality = "offline"
    elif latency > SLOW_LATENCY_MS or (mbps is not None and mbps < SLOW_MBPS):
        quality = "slow"
    else:
        quality = "fast"
    return {"quality": quality, "latency_ms": round(latency) if latency else None,
            "mbps": round(mbps, 1) if mbps else None, "checked": time.time()}


def refresh():
    with _lock:
        before = state["quality"]
        state.update(measure())
    if state["quality"] != before:
        for fn in _listeners:
            fn(dict(state))


def effective() -> str:
    """The mode NEXUS acts on right now: offline | hybrid | online."""
    mode = settings.get("network_mode", "auto")
    if mode != "auto":
        return mode
    return {"offline": "offline", "slow": "hybrid", "fast": "online"}.get(state["quality"], "hybrid")


def report_failure():
    """An online call failed: measure again soon instead of waiting for the next round."""
    if settings.get("network_mode") == "auto" and time.time() - state["checked"] > 20:
        threading.Thread(target=refresh, daemon=True, name="netprobe").start()


def start(on_change=None):
    if on_change:
        _listeners.append(on_change)

    def loop():
        from . import legal

        while True:
            if settings.get("network_mode") == "auto" and legal.accepted():  # v0.17.0: nothing online before consent
                try:
                    refresh()
                except Exception:
                    pass
            time.sleep(PROBE_EVERY)

    threading.Thread(target=loop, daemon=True, name="netprobe").start()
