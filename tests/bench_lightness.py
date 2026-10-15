"""v0.14 lightness: what the caches and the background release actually save.
Run: .venv\\Scripts\\python tests\\bench_lightness.py   (needs internet for the online cache part)"""
import _isolated  # noqa: F401

import ctypes
import gc
import time
from ctypes import wintypes

from nexus import knowledge, tools, tts, voice
from nexus.config import settings


def rss_mb() -> float:
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 2 ** 20


print("1) VOZ — frase repetida (síntese + efeito)")
engine = tts.Engine()
speaker = voice.Speaker.__new__(voice.Speaker)
v, pitch = engine.pick("pt", "male")
for phrase in ("Executando em modo Direto.", "Acho que não entendeu, vou repetir."):
    t0 = time.perf_counter(); speaker._render(engine, tts, phrase, v, pitch); first = time.perf_counter() - t0
    t0 = time.perf_counter(); speaker._render(engine, tts, phrase, v, pitch); again = time.perf_counter() - t0
    print(f"   {phrase!r}: 1ª vez {first * 1000:.0f} ms | repetida {again * 1000:.2f} ms")

print("\n2) BASE DE CONHECIMENTO — mesma busca")
knowledge.load_seed()
for q in ("como fazer RCP", "o que é estoicismo"):
    knowledge._cache.clear()
    t0 = time.perf_counter(); knowledge.search(q); first = time.perf_counter() - t0
    t0 = time.perf_counter(); knowledge.search(q); again = time.perf_counter() - t0
    print(f"   {q!r}: 1ª vez {first * 1000:.1f} ms | repetida {again * 1000:.3f} ms")

print("\n3) ONLINE — mesma pergunta em seguida")
settings["home_city"] = "São Paulo"
for name, args in (("get_weather", {}), ("convert_currency", {"amount": 100, "from_currency": "USD", "to_currency": "BRL"})):
    t0 = time.perf_counter(); r1 = tools.execute(name, args); first = time.perf_counter() - t0
    t0 = time.perf_counter(); tools.execute(name, args); again = time.perf_counter() - t0
    ok = "error" not in r1
    print(f"   {name}: 1ª vez {first * 1000:.0f} ms | repetida {again * 1000:.2f} ms" + ("" if ok else f"  ({r1})"))

print("\n4) MINIMIZADO — memória liberada pelo Whisper small")
from faster_whisper import WhisperModel  # noqa: E402

gc.collect(); base = rss_mb()
model = WhisperModel("small", device="cpu", compute_type="int8", local_files_only=True)
loaded = rss_mb()
del model; gc.collect()
freed = rss_mb()
print(f"   antes {base:.0f} MB | com Whisper {loaded:.0f} MB (+{loaded - base:.0f}) | liberado {freed:.0f} MB "
      f"(-{loaded - freed:.0f} MB)")
