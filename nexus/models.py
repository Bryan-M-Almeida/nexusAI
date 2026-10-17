"""Local models (v0.18.6): which NEXUS model fits this PC, download with progress, switch with one click.

The catalog goes from NEX-1.0 Lite (1.7B, runs even without a graphics card) to NEX-1.0 Max (30B mixture of
experts). How much of a model fits on the card is estimated from its size at 8k context (measured with Ollama on
the reference PC, tests/bench_models.py) against this PC's usable video memory; what doesn't fit goes to the RAM
and the answers get slower. MEASURED holds the reference PC's numbers (RX 6600 XT 8 GB, Ryzen 5 5600G, 16 GB)."""
import json
import threading

import httpx

from . import hardware, llm
from .config import settings

CATALOG = [  # id, display name, tier, file size GB, total size on the card at 8k context GB (weights + cache + buffers;
    # measured with Ollama 0.40.5 for 1.7b / 4b / 8b / 14b, estimated for the 30b)
    {"id": "qwen3:1.7b", "name": "NEX-1.0 Lite", "tier": "lite", "file_gb": 1.4, "run_gb": 2.5},
    # "qwen3:4b" is the 2507 *thinking* model: it reasons for 20-40 s before every answer (69.6 s average in the eval)
    # and can't be told not to; the instruct build of the same model answers directly.
    {"id": "qwen3:4b-instruct-2507-q4_K_M", "name": "NEX-1.0 Mini", "tier": "mini", "file_gb": 2.5, "run_gb": 5.6},
    {"id": "qwen3:8b", "name": "NEX-1.0", "tier": "standard", "file_gb": 5.2, "run_gb": 6.6},
    {"id": "qwen3:14b", "name": "NEX-1.0 Pro", "tier": "pro", "file_gb": 9.3, "run_gb": 10.7},
    {"id": "qwen3:30b-a3b", "name": "NEX-1.0 Max", "tier": "max", "file_gb": 18.6, "run_gb": 19.8},
]
BY_ID = {m["id"]: m for m in CATALOG}
# Reference PC (Ryzen 5 5600G, 16 GB, RX 6600 XT 8 GB, Ollama 0.40.5/Vulkan), tests/bench_models.py 2026-10-16:
# the full conversation eval (37 checks) with each model.
MEASURED: dict = {
    "qwen3:1.7b": {"on_gpu_pct": 100, "cold_start_s": 5.3, "tok_s": 30.2, "first_s": 0.4, "avg_answer_s": 2.84, "checks": "32/37"},
    "qwen3:4b-instruct-2507-q4_K_M": {"on_gpu_pct": 100, "cold_start_s": 17.9, "tok_s": 24.2, "first_s": 2.7,
                                      "avg_answer_s": 6.56, "checks": "36/37"},
    "qwen3:8b": {"on_gpu_pct": 92, "cold_start_s": 14.5, "tok_s": 21.4, "first_s": 1.5, "avg_answer_s": 5.48, "checks": "37/37"},
    "qwen3:14b": {"on_gpu_pct": 58, "cold_start_s": 31.8, "tok_s": 7.3, "first_s": 3.9, "avg_answer_s": 12.88, "checks": "37/37"},
}
RAM_FOR_SYSTEM_GB = 6.0  # Windows + NEXUS + browser keep about this much


def display_name(model_id: str | None = None) -> str:
    model_id = model_id or settings.get("llm_model", "")
    m = BY_ID.get(model_id)
    return m["name"] if m else ("NEX-1.0" if not model_id else f"NEX · {model_id}")


def fit(model: dict, vram_gb: float | None = None, ram_gb: float | None = None) -> dict:
    """How this model runs here: "gpu" (all on the card), "partial" (part in RAM, slower), "cpu" (no usable card),
    "no" (doesn't fit in card + RAM)."""
    ram = hardware.ram_gb() if ram_gb is None else ram_gb
    if vram_gb is None:  # Ollama splits a model across several dedicated cards by itself: their memory adds up
        usable = sum(max(0.0, g["vram_gb"] - hardware.VRAM_RESERVED_GB) for g in hardware.gpus() if g["vram_gb"] >= 2)
    else:
        usable = max(0.0, vram_gb - hardware.VRAM_RESERVED_GB) if vram_gb >= 2 else 0.0
    need = model["run_gb"]
    on_gpu = min(1.0, usable / need) if need else 0.0
    spill = max(0.0, need - usable)
    if spill > max(0.0, ram - RAM_FOR_SYSTEM_GB):
        status = "no"
    elif usable == 0:
        status = "cpu"
    elif on_gpu >= 0.9:  # the 8B runs 92% on an 8 GB card (flash attention off) at full speed
        status = "gpu"
    else:
        status = "partial"
    return {"status": status, "on_gpu_pct": round(100 * on_gpu), "need_gb": need, "usable_vram_gb": round(usable, 1)}


def recommended(vram_gb: float | None = None, ram_gb: float | None = None) -> str:
    """The largest model that runs (almost) entirely on the card: all of it, or at least 75% when that is a bigger
    model (on a 6 GB card the Mini at ~75% answers better than the Lite: 36/37 vs 32/37 in the eval). Without a
    usable card, the small ones on the processor."""
    best = None
    for m in CATALOG:  # ordered from the smallest
        f = fit(m, vram_gb, ram_gb)
        if f["status"] == "gpu" or (f["status"] == "partial" and f["on_gpu_pct"] >= 75):
            best = m["id"]
    if best:
        return best
    ram = hardware.ram_gb() if ram_gb is None else ram_gb
    return "qwen3:4b-instruct-2507-q4_K_M" if ram >= 12 else "qwen3:1.7b"


def installed() -> set[str]:
    try:
        tags = httpx.get(f"{llm._ollama_root()}/api/tags", timeout=4).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return set()
    names = set()
    for t in tags:
        names.add(t.get("name", ""))
        names.add(t.get("model", ""))
    return {n for n in names if n}


def catalog() -> dict:
    have, current, rec = installed(), settings.get("llm_model", ""), recommended()
    rows = []
    for m in CATALOG:
        rows.append({**m, **fit(m), "installed": m["id"] in have, "active": m["id"] == current,
                     "recommended": m["id"] == rec, "measured": MEASURED.get(m["id"])})
    return {"models": rows, "active": current, "recommended": rec, "pc": {"vram_gb": hardware.best_vram_gb(),
                                                                         "ram_gb": hardware.ram_gb()},
            "pulling": dict(_pull)}


# ---------------------------------------------------------------- download (Ollama /api/pull)
_pull: dict = {}  # {"id", "pct", "status", "error"} while a download runs


def pull(model_id: str, progress=lambda pct: None) -> dict:
    """Download a catalog model through Ollama, reporting 0..100. Blocking (run it in a thread)."""
    if model_id not in BY_ID:
        return {"ok": False, "error": "unknown model"}
    if _pull.get("id"):
        return {"ok": False, "error": "busy"}
    _pull.update(id=model_id, pct=0, status="starting", error="")
    from . import downloads

    did = downloads.start("model", model_id, int(BY_ID[model_id]["file_gb"] * 2 ** 30))
    last = -1
    try:
        with httpx.stream("POST", f"{llm._ollama_root()}/api/pull", json={"model": model_id, "stream": True},
                          timeout=httpx.Timeout(60, read=600)) as r:
            for line in r.iter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                _pull["status"] = chunk.get("status", "")
                total, done = chunk.get("total") or 0, chunk.get("completed") or 0
                if total > 50 * 2 ** 20:
                    downloads.update(did, done, total)
                elif chunk.get("status") and not total:
                    downloads.update(did, 0, None, note=chunk["status"])  # "pulling manifest", "verifying sha256 digest"...
                if total > 50 * 2 ** 20:  # the big layer (the weights) drives the percentage
                    pct = min(99, int(100 * done / total))
                    if pct != last:
                        last = pct
                        _pull["pct"] = pct
                        progress(pct)
        progress(100)
        downloads.finish(did, True)
        return {"ok": True, "id": model_id}
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        downloads.finish(did, False, str(exc))
        _pull["error"] = str(exc)[:200]
        progress(-1)
        return {"ok": False, "error": str(exc)[:200]}
    finally:
        _pull.clear()


def use(model_id: str) -> dict:
    """Switch the active model: the old one leaves the card, the new one is loaded in the background."""
    if model_id not in installed():
        return {"ok": False, "error": "not installed"}
    old = settings.get("llm_model")
    if old and old != model_id:
        llm.unload()
    settings.apply({"llm_model": model_id})
    return {"ok": True, "id": model_id, "name": display_name(model_id)}


def pull_async(model_id: str, progress) -> dict:
    if _pull.get("id"):
        return {"ok": False, "error": "busy"}
    threading.Thread(target=pull, args=(model_id, progress), daemon=True, name="model-pull").start()
    return {"ok": True}
