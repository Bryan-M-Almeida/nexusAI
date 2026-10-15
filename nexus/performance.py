"""Performance profiles (v0.12). Choosing a profile writes a coherent set of settings; the user can still fine-tune
each one afterwards in Settings. "Força total" (max) is only offered when the model + a large context fit entirely
in the graphics card's memory - spilling layers to the CPU makes every answer several times slower
(see tests/bench_hardware.py and CHANGELOG v0.12)."""
from . import hardware

PROFILES = ("economy", "balanced", "max")
MIN_RAM_GB = 15        # "16 GB" machines report ~15.8 GB
MAX_PROFILE_CTX = 16384


def max_allowed() -> tuple[bool, str]:
    """(allowed, reason) for "Força total"."""
    hw = hardware.summary()
    if hw["ram_gb"] and hw["ram_gb"] < MIN_RAM_GB:
        return False, f"ram:{hw['ram_gb']}"
    ctx = hardware.max_context()
    if ctx < 8192:  # full power = everything on the GPU with at least the balanced context
        return False, f"vram:{hw['vram_gb']}"
    return True, ""


def settings_for(profile: str) -> dict:
    if profile == "economy":
        # Lighter on everything: smaller context, faster speech recognition, model released sooner, no extra AI calls.
        return {"llm_context": 4096, "history_turns": 6, "stt_model": "base", "stt_beam": 1, "llm_keep_alive": "10m",
                "llm_num_gpu": -1, "auto_title": False, "reduce_motion": True, "show_hud": False, "performance": "economy"}
    if profile == "max":
        ok, _ = max_allowed()
        if not ok:
            return settings_for("balanced")
        ctx = min(MAX_PROFILE_CTX, hardware.max_context())
        return {"llm_context": ctx, "history_turns": 20, "stt_model": "medium", "stt_beam": 5, "llm_keep_alive": "8h",
                "llm_num_gpu": 999, "auto_title": True, "reduce_motion": False, "show_hud": True, "performance": "max"}
    return {"llm_context": 8192, "history_turns": 12, "stt_model": "small", "stt_beam": 5, "llm_keep_alive": "2h",
            "llm_num_gpu": -1, "auto_title": True, "reduce_motion": False, "show_hud": True, "performance": "balanced"}


# Requirements published in the README (measured on the reference PC; see CHANGELOG v0.12).
REQUIREMENTS = {
    "minimum": {"ram_gb": 15, "vram_gb": 0, "cores": 8, "disk_gb": 10},      # CPU only: works, ~5x slower
    "recommended": {"ram_gb": 15, "vram_gb": 8, "cores": 8, "disk_gb": 12},  # everything on the GPU
}


def check() -> dict:
    hw = hardware.summary()
    out = {"hardware": hw, "max_allowed": max_allowed()[0], "max_reason": max_allowed()[1],
           "max_context": hardware.max_context()}
    for level, req in REQUIREMENTS.items():
        out[level] = (hw["ram_gb"] >= req["ram_gb"] and hw["cores"] >= req["cores"]
                      and hw["vram_gb"] >= req["vram_gb"])
    return out
