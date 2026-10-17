"""AMD panel (v0.18.5): what the graphics card is doing for NEXUS, in the spirit of AMD Software: Adrenalin Edition's
performance overlay, read without extra software:
  - the card, driver and Adrenalin version from the registry (the same keys the AMD driver installs);
  - live load and memory from Windows' performance counters (PDH: the numbers Task Manager shows), per engine
    (3D, Compute...) and per process, so the panel separates what the AI (Ollama) uses from the rest;
  - the AI's own speed (tokens/s, prompt reading, time to the first word) recorded from every answer (llm.STATS).
Temperature and clocks need AMD's ADLX library; the panel points to Adrenalin (Alt+R) for those."""
import ctypes
import os
import re
import threading
import time
import winreg
from ctypes import wintypes

DISPLAY_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


def _reg(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def info() -> dict:
    """The AMD/Radeon card(s) from the driver's registry keys."""
    cards = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, DISPLAY_CLASS)
    except OSError:
        return {"cards": []}
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(root, i)
        except OSError:
            break
        i += 1
        if not sub.isdigit():
            continue
        try:
            k = winreg.OpenKey(root, sub)
        except OSError:
            continue
        name = _reg(k, "DriverDesc") or ""
        if not re.search(r"amd|radeon", name, re.I):
            continue
        vram = _reg(k, "HardwareInformation.qwMemorySize") or _reg(k, "HardwareInformation.MemorySize") or 0
        if isinstance(vram, bytes):
            vram = int.from_bytes(vram, "little")
        cards.append({"name": name, "vram_gb": round(int(vram) / 2 ** 30, 1), "driver": _reg(k, "DriverVersion") or "",
                      "driver_date": _reg(k, "DriverDate") or "",
                      "adrenalin": _reg(k, "RadeonSoftwareVersion") or _reg(k, "Catalyst_Version") or "",
                      "edition": _reg(k, "RadeonSoftwareEdition") or ""})
    return {"cards": cards}


# ---------------------------------------------------------------- PDH (Windows performance counters)
PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2


class _Value(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _Item(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _Value)]


class _Counters:
    """One PDH query with the GPU counters; collect() twice a little apart gives rates (utilisation)."""
    PATHS = {"engine": r"\GPU Engine(*)\Utilization Percentage",
             "adapter_dedicated": r"\GPU Adapter Memory(*)\Dedicated Usage",
             "adapter_shared": r"\GPU Adapter Memory(*)\Shared Usage",
             "process_dedicated": r"\GPU Process Memory(*)\Dedicated Usage"}

    def __init__(self):
        self.pdh = ctypes.WinDLL("pdh")
        for fn in ("PdhOpenQueryW", "PdhAddEnglishCounterW", "PdhCollectQueryData", "PdhGetFormattedCounterArrayW"):
            getattr(self.pdh, fn).restype = ctypes.c_uint32  # PDH_STATUS is unsigned (PDH_MORE_DATA = 0x800007D2)
        self.query = wintypes.HANDLE()
        if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.query)):
            raise OSError("PdhOpenQuery failed")
        self.counters = {}
        for key, path in self.PATHS.items():
            h = wintypes.HANDLE()
            if self.pdh.PdhAddEnglishCounterW(self.query, path, None, ctypes.byref(h)) == 0:
                self.counters[key] = h
        self.pdh.PdhCollectQueryData(self.query)

    def array(self, key) -> dict[str, float]:
        h = self.counters.get(key)
        if h is None:
            return {}
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        status = self.pdh.PdhGetFormattedCounterArrayW(h, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None)
        if status != PDH_MORE_DATA or not size.value:
            return {}
        buf = (ctypes.c_byte * size.value)()
        if self.pdh.PdhGetFormattedCounterArrayW(h, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), buf):
            return {}
        items = ctypes.cast(buf, ctypes.POINTER(_Item))
        return {items[i].szName: items[i].FmtValue.doubleValue for i in range(count.value) if items[i].FmtValue.CStatus in (0, 1)}

    def collect(self):
        self.pdh.PdhCollectQueryData(self.query)


_pdh: _Counters | None = None
_lock = threading.Lock()


def _ollama_pids() -> set[int]:
    """Process ids of Ollama and its runner (llama-server.exe in recent versions: it holds the model on the card)."""
    import subprocess

    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5,
                             creationflags=0x08000000).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {int(m.group(2)) for m in re.finditer(r'^"([^"]+)","(\d+)"', out, re.M) if re.search(r"ollama|llama-server", m.group(1), re.I)}


_pids_cache: tuple[float, set] = (0.0, set())


def live() -> dict:
    """Load and memory now. The first call primes the counters (utilisation needs two samples ~0.25 s apart)."""
    global _pdh, _pids_cache
    with _lock:
        try:
            first = _pdh is None
            if first:
                _pdh = _Counters()
                time.sleep(0.25)
            _pdh.collect()
            engines = _pdh.array("engine")
            dedicated = _pdh.array("adapter_dedicated")
            shared = _pdh.array("adapter_shared")
            per_proc = _pdh.array("process_dedicated")
        except OSError as exc:
            return {"error": str(exc)}
    by_type: dict[str, float] = {}
    by_pid: dict[int, float] = {}
    for name, value in engines.items():
        m = re.search(r"pid_(\d+).*engtype_(.+)$", name)
        if not m:
            continue
        by_type[m.group(2)] = by_type.get(m.group(2), 0) + value
        by_pid[int(m.group(1))] = by_pid.get(int(m.group(1)), 0) + value
    if time.time() - _pids_cache[0] > 15:
        _pids_cache = (time.time(), _ollama_pids())
    ai_pids = _pids_cache[1]
    ai_vram = sum(v for n, v in per_proc.items() if (m := re.search(r"pid_(\d+)", n)) and int(m.group(1)) in ai_pids)
    me = os.getpid()
    return {
        "gpu_pct": round(min(100.0, max(by_type.values(), default=0.0)), 1),  # Task Manager: the busiest engine type
        "engines": {k: round(min(100.0, v), 1) for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])[:4]},
        "ai_gpu_pct": round(min(100.0, sum(v for p, v in by_pid.items() if p in ai_pids)), 1),
        "nexus_gpu_pct": round(min(100.0, by_pid.get(me, 0.0)), 1),
        "vram_used_mb": round(max(dedicated.values(), default=0) / 2 ** 20),
        "shared_used_mb": round(max(shared.values(), default=0) / 2 ** 20),
        "ai_vram_mb": round(ai_vram / 2 ** 20),
        "ts": time.time(),
    }


# ---------------------------------------------------------------- ROCm and NPU (v0.19.5)
# Radeon name -> chip (LLVM target). ROCm needs libraries built for each chip; Ollama ships them for some only.
GFX = [(r"RX 9070", "gfx1201"), (r"RX 9060", "gfx1200"), (r"RX 79\d0|RX 7900|PRO W7900|PRO W7800", "gfx1100"),
       (r"RX 7800|RX 7700|PRO W7700", "gfx1101"), (r"RX 7600|PRO W7600|PRO W7500", "gfx1102"),
       (r"Radeon 8\d0M|880M|890M", "gfx1150"), (r"Radeon 8060S|8050S", "gfx1151"), (r"780M|760M|740M", "gfx1103"),
       (r"RX 69\d0|RX 6800|PRO W6800", "gfx1030"), (r"RX 6700|RX 6750", "gfx1031"),
       (r"RX 66\d0|RX 6600|PRO W6600", "gfx1032"), (r"RX 65\d0|RX 6400|RX 6500", "gfx1034"),
       (r"Radeon VII|Instinct MI50|MI60", "gfx906"), (r"Instinct MI100", "gfx908"), (r"Instinct MI2\d0", "gfx90a"),
       (r"Instinct MI3\d0", "gfx942")]


def gfx(card_name: str) -> str:
    return next((g for rx, g in GFX if re.search(rx, card_name, re.I)), "")


def rocm_targets() -> set[str]:
    """Chips the ROCm bundled with Ollama has libraries for - read from the installation itself, so a newer Ollama
    with more chips is recognised without changing NEXUS."""
    from . import gpu_tune

    found = set()
    for lib in gpu_tune.OLLAMA_DIR.glob("lib/ollama/rocm*/rocblas/library/*"):
        found.update(re.findall(r"gfx[0-9a-f]{3,4}", lib.name))
    return found


def rocm_support(card_name: str) -> dict:
    """{"gfx", "supported", "targets"} for this card with the Ollama installed here."""
    chip, targets = gfx(card_name), rocm_targets()
    return {"gfx": chip, "supported": bool(chip and chip in targets), "targets": sorted(targets),
            "installed": bool(targets)}


_npu_cache: list | None = None


def npus() -> list[str]:
    """Neural processors Windows knows (AMD Ryzen AI "NPU Compute Accelerator", Intel AI Boost, Snapdragon...)."""
    global _npu_cache
    if _npu_cache is None:
        import subprocess

        try:
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-PnpDevice -PresentOnly | "
                                  "Where-Object { $_.FriendlyName -match 'NPU|IPU|AI Boost|Neural|XDNA' } | "
                                  "ForEach-Object { $_.FriendlyName }"],
                                 capture_output=True, text=True, timeout=15, creationflags=0x08000000, encoding="utf-8",
                                 errors="replace").stdout
            _npu_cache = [line.strip() for line in out.splitlines() if line.strip()]
        except Exception:
            _npu_cache = []
    return _npu_cache


LEMONADE_URLS = ("http://127.0.0.1:8000/api/v1", "http://127.0.0.1:13305/api/v1")


def lemonade() -> dict:
    """AMD Lemonade Server (runs models on the Ryzen AI NPU / iGPU, OpenAI-compatible): running here? which models?"""
    import httpx

    for url in LEMONADE_URLS:
        try:
            data = httpx.get(f"{url}/models", timeout=1.5).json()
            return {"running": True, "url": url, "models": [m.get("id", "") for m in data.get("data", [])][:30]}
        except Exception:
            continue
    return {"running": False, "url": LEMONADE_URLS[0], "models": []}


def technologies() -> list[dict]:
    """AMD technologies in NEXUS on this PC: "active", "available" (would work here) or "unsupported" (with why)."""
    from . import gpu_tune, hardware

    cards = info()["cards"]
    tune = gpu_tune.status()
    cpu = hardware.cpu_name()
    name = cards[0]["name"] if cards else ""
    rocm = rocm_support(name)
    npu_list = npus()
    lem = lemonade() if npu_list or re.search(r"ryzen ai", cpu, re.I) else {"running": False}
    out = [
        {"id": "radeon_vulkan", "status": "active" if cards and tune["vulkan"] else ("available" if cards else "unsupported"),
         "detail": name},
        {"id": "rocm", "status": "active" if cards and not tune["vulkan"] and rocm["supported"]
         else ("available" if rocm["supported"] else "unsupported"),
         "detail": f"{name} ({rocm['gfx'] or '?'})", "gfx": rocm["gfx"], "targets": rocm["targets"]},
        {"id": "adrenalin", "status": "active" if cards and cards[0]["adrenalin"] else "unsupported",
         "detail": cards[0]["adrenalin"] if cards else ""},
        {"id": "ryzen_cpu", "status": "active" if "ryzen" in cpu.lower() else "unsupported", "detail": cpu},
        {"id": "ryzen_ai", "status": "active" if lem.get("running") and settings_llm_is_lemonade()
         else ("available" if npu_list or re.search(r"ryzen ai", cpu, re.I) else "unsupported"),
         "detail": ", ".join(npu_list) or cpu, "lemonade": lem},
        {"id": "amd_counters", "status": "active" if cards else "unsupported", "detail": ""},
    ]
    return out


def settings_llm_is_lemonade() -> bool:
    from .config import settings

    return settings.get("llm_preset") == "lemonade"


REFERENCES = [  # shown in the AMD tab; only these addresses can be opened from it
    ("adrenalin", "https://www.amd.com/en/products/software/adrenalin.html"),
    ("rocm", "https://rocm.docs.amd.com/"),
    ("gpuopen", "https://gpuopen.com/"),
    ("developer", "https://www.amd.com/en/developer.html"),
    ("ryzen_ai", "https://www.amd.com/en/products/processors/consumer/ryzen-ai.html"),
    ("ollama_amd", "https://ollama.com/blog/amd-preview"),
    ("lemonade", "https://lemonade-server.ai/"),
    ("hackathon", "https://lablab.ai/"),
]


def open_reference(ref_id: str) -> bool:
    url = dict(REFERENCES).get(ref_id)
    if not url:
        return False
    os.startfile(url)
    return True
