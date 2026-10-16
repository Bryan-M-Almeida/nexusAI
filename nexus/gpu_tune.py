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


def _get() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, VAR)[0])
    except OSError:
        return None


def _set(value: str | None):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        if value is None:
            try:
                winreg.DeleteValue(k, VAR)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(k, VAR, 0, winreg.REG_SZ, value)
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

    for name in ("ollama app.exe", "ollama.exe"):
        subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, creationflags=0x08000000)
    time.sleep(1.5)
    env = os.environ.copy()
    if flash_off:
        env[VAR] = "0"
    else:
        env.pop(VAR, None)
    subprocess.Popen([str(OLLAMA_DIR / "ollama app.exe")], env=env, creationflags=0x00000008 | 0x08000000)
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            httpx.get("http://127.0.0.1:11434/api/version", timeout=2)
            return True
        except Exception:
            time.sleep(0.7)
    return False


def apply(on: bool) -> dict:
    _set("0" if on else None)
    ok = restart_ollama(on) if status()["installed"] else False
    return {**status(), "restarted": ok}
