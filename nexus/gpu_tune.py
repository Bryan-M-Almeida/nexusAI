"""Settings > Performance > "Optimize Ollama for this graphics card" (v0.17.0).

Ollama runs AMD cards without ROCm support (e.g. RX 6600 XT, gfx1032, on Windows) through Vulkan. There its Flash
Attention reads prompts at ~75 tokens/s against ~265 with it off (measured on an RX 6600 XT, 5,500 tokens); in a real
8-question conversation answers went from 16.4 s to 11.9 s (-27%, Ollama 0.40.4) and from 14.2 s to 9.0 s (-37%,
Ollama 0.40.5), with generation ~30% slower and ~0.5 GB of the
model moving to RAM. Turning it off is the user-level environment variable OLLAMA_FLASH_ATTENTION=0, read by Ollama
when it starts - so the change only happens when the user asks, is fully reversible and Ollama is restarted.
NVIDIA cards (and AMD with ROCm) are faster WITH Flash Attention: the option is only offered for AMD + Vulkan."""
import os
import pathlib
import subprocess
import time

from . import hardware

VAR = "OLLAMA_FLASH_ATTENTION"
OLLAMA_DIR = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
OLLAMA_LOG = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "server.log"


def _get(var: str = VAR) -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, var)[0])
    except OSError:
        return None


def _set(value: str | None, var: str = VAR):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        if value is None:
            try:
                winreg.DeleteValue(k, var)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(k, var, 0, winreg.REG_SZ, value)
    try:  # tell Windows (Explorer, the tray) that the environment changed
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 5000, None)
    except Exception:
        pass


def uses_vulkan() -> bool:
    """Ollama logs which backend it chose when it starts ("library=Vulkan")."""
    try:
        with OLLAMA_LOG.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400_000))
            text = f.read().decode("utf-8", "ignore")
        return "library=Vulkan" in text and "library=ROCm" not in text[text.rfind("inference compute"):]
    except OSError:
        return False


def status() -> dict:
    amd = any(("amd" in g["name"].lower() or "radeon" in g["name"].lower()) for g in hardware.gpus())
    vulkan = uses_vulkan()
    return {"amd": amd, "vulkan": vulkan, "applied": _get() == "0", "suggest": amd and vulkan,
            "installed": (OLLAMA_DIR / "ollama app.exe").exists()}


def restart_ollama(flash_off: bool, wait: float = 25.0) -> bool:
    """Close Ollama and open it again with the new setting. Returns True when it answers again."""
    import httpx

    for name in ("ollama app.exe", "ollama.exe", "llama-server.exe"):  # llama-server: the runner of newer Ollama
        subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, creationflags=0x08000000)
    time.sleep(1.5)
    env = os.environ.copy()
    if flash_off:
        env[VAR] = "0"
    else:
        env.pop(VAR, None)
    backend_value = _get(BACKEND_VAR)  # v0.19.5: the backend choice saved for the user reaches the new Ollama too
    if backend_value is None:
        env.pop(BACKEND_VAR, None)
    else:
        env[BACKEND_VAR] = backend_value
    subprocess.Popen([str(OLLAMA_DIR / "ollama app.exe")], env=env, creationflags=0x00000008 | 0x08000000)
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            httpx.get("http://127.0.0.1:11434/api/version", timeout=2)
            return True
        except Exception:
            time.sleep(0.7)
    return False


# ---------------------------------------------------------------- backend: Vulkan or ROCm (v0.19.5)
# Ollama on Windows has both. "rocm" = the user variable OLLAMA_VULKAN=0, so Ollama uses ROCm on cards it has ROCm
# libraries for (see amd.rocm_support); "auto" removes it. On a card without them ROCm finds no device and Ollama
# falls back to the processor - measured on an RX 6600 XT (gfx1032): 9.1 tok/s with 0% on the card against 35.6 tok/s
# with Vulkan - so NEXUS only offers ROCm where it works.
BACKEND_VAR = "OLLAMA_VULKAN"


def backend() -> str:
    return "rocm" if _get(BACKEND_VAR) == "0" else "auto"


def set_backend(choice: str) -> dict:
    from . import amd

    card = (amd.info()["cards"] or [{}])[0].get("name", "")
    if choice == "rocm" and not amd.rocm_support(card)["supported"]:
        return {"ok": False, "error": "unsupported"}
    _set("0" if choice == "rocm" else None, BACKEND_VAR)
    ok = restart_ollama(_get() == "0") if status()["installed"] else False
    return {"ok": True, "backend": backend(), "restarted": ok}


def _measure(model: str) -> dict:
    import httpx

    body = {"model": model, "stream": False, "think": False, "options": {"num_ctx": 8192},
            "messages": [{"role": "user", "content": "Explique em 5 frases o que é uma GPU."}]}
    r = httpx.post("http://127.0.0.1:11434/api/chat", json=body, timeout=600).json()
    ps = httpx.get("http://127.0.0.1:11434/api/ps", timeout=5).json().get("models", [])
    ev, evd = r.get("eval_count") or 0, r.get("eval_duration") or 1
    size = (ps[0].get("size") or 1) if ps else 1
    return {"tok_s": round(ev / (evd / 1e9), 1), "load_s": round((r.get("load_duration") or 0) / 1e9, 1),
            "on_gpu_pct": round(100 * (ps[0].get("size_vram") or 0) / size) if ps else 0}


def compare_backends(model: str) -> dict:
    """Same question with ROCm and with Vulkan (Ollama restarted for each, then back to the user's choice)."""
    from . import amd

    card = (amd.info()["cards"] or [{}])[0].get("name", "")
    if not amd.rocm_support(card)["supported"]:
        return {"ok": False, "error": "unsupported"}
    previous = _get(BACKEND_VAR)
    out = {}
    try:
        for name, value in (("rocm", "0"), ("vulkan", None)):
            _set(value, BACKEND_VAR)
            if not restart_ollama(_get() == "0"):
                return {"ok": False, "error": "restart"}
            out[name] = _measure(model)
    finally:
        _set(previous, BACKEND_VAR)
        restart_ollama(_get() == "0")
    best = max(out, key=lambda k: out[k]["tok_s"] * (1 if out[k]["on_gpu_pct"] else 0.1))
    return {"ok": True, **out, "best": best}


def apply(on: bool) -> dict:
    _set("0" if on else None)
    ok = restart_ollama(on) if status()["installed"] else False
    return {**status(), "restarted": ok}
