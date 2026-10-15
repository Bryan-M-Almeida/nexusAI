"""Hardware detection (v0.12) for the performance profiles and the requirements check. Windows only parts fail
silently elsewhere. Everything here is cheap (< 50 ms) and cached."""
import ctypes
import functools
import os
import platform


@functools.lru_cache(maxsize=1)
def ram_gb() -> float:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return round(stat.ullTotalPhys / 2 ** 30, 1)
    except Exception:
        return 0.0


@functools.lru_cache(maxsize=1)
def gpus() -> list[dict]:
    """Display adapters with their real VRAM. The registry value qwMemorySize is 64-bit; WMI's AdapterRAM is
    32-bit and reports at most 4 GB, which would wrongly block "full power" on an 8 GB card."""
    out = []
    try:
        import winreg

        key = r"SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as root:
            for i in range(64):
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(root, sub) as k:
                        name = winreg.QueryValueEx(k, "DriverDesc")[0]
                        try:
                            vram = int(winreg.QueryValueEx(k, "HardwareInformation.qwMemorySize")[0])
                        except OSError:
                            raw = winreg.QueryValueEx(k, "HardwareInformation.MemorySize")[0]
                            vram = int.from_bytes(raw, "little") if isinstance(raw, bytes) else int(raw)
                        out.append({"name": name, "vram_gb": round(vram / 2 ** 30, 1)})
                except OSError:
                    continue
    except Exception:
        pass
    return [g for g in out if "basic" not in g["name"].lower() and "virtual" not in g["name"].lower()]


def best_vram_gb() -> float:
    return max((g["vram_gb"] for g in gpus()), default=0.0)


@functools.lru_cache(maxsize=1)
def cpu_name() -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception:
        return platform.processor() or platform.machine()


def summary() -> dict:
    return {"os": f"{platform.system()} {platform.release()}", "cpu": cpu_name(),
            "cores": os.cpu_count() or 1, "ram_gb": ram_gb(), "gpus": gpus(), "vram_gb": best_vram_gb()}


# Measured on the reference PC (tests/bench_hardware.py, RX 6600 XT 8 GB, qwen3:8b Q4_K_M, Ollama/Vulkan):
#   ctx  4096 -> 5.19 GB, 100% on GPU, writes 40 tok/s      ctx 12288 -> 6.71 GB,  92% on GPU, 31 tok/s
#   ctx  8192 -> 5.75 GB, 100% on GPU, writes 35 tok/s      ctx 16384 -> 7.28 GB,  85% on GPU, 25 tok/s
#   CPU only (ctx 4096): writes 7.5 tok/s, reads 47 tok/s (~5x slower than the GPU)
# Only ~6.2 GB of the 8 GB card were usable (driver/desktop keep the rest), so the usable VRAM is taken as
# total - 1.8 GB. Anything that doesn't fit spills layers to the CPU: answers get up to 2x slower.
MODEL_SIZE_GB = {4096: 5.19, 8192: 5.75, 12288: 6.71, 16384: 7.28, 32768: 9.6}  # 32k extrapolated
VRAM_RESERVED_GB = 1.8


def fits_in_vram(context: int, vram: float | None = None) -> bool:
    vram = best_vram_gb() if vram is None else vram
    return MODEL_SIZE_GB[context] <= vram - VRAM_RESERVED_GB


def max_context(vram: float | None = None) -> int:
    """Largest standard context that still fits fully in VRAM (0 = the model itself doesn't fit)."""
    for ctx in (32768, 16384, 12288, 8192, 4096):
        if fits_in_vram(ctx, vram):
            return ctx
    return 0
