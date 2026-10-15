"""Measures what the performance profiles and the minimum requirements are based on (v0.12).
- AI (Ollama): for each context size, is the model fully on the GPU, and how fast does it read and write?
- AI on the CPU only (num_gpu 0): the "no graphics card" case.
- Voice: Whisper load time / RAM and transcription speed.
Run: .venv\\Scripts\\python tests\\bench_hardware.py   (several minutes; unloads the model between runs)"""
import _isolated  # noqa: F401

import os
import time

import httpx

from nexus import hardware, llm
from nexus.config import settings

ROOT = "http://127.0.0.1:11434"
MODEL = settings["llm_model"]
PROMPT = ("Explique em português, em cerca de 120 palavras, o que é uma variável em programação e dê um exemplo. "
          + "Contexto: " + "NEXUS é um assistente pessoal local. " * 120)  # ~1.2k tokens of input


def unload():
    httpx.post(f"{ROOT}/api/generate", json={"model": MODEL, "keep_alive": 0}, timeout=60)
    time.sleep(2)


def run(ctx, num_gpu=None):
    unload()
    opts = {"num_ctx": ctx, "temperature": 0, "num_predict": 160}
    if num_gpu is not None:
        opts["num_gpu"] = num_gpu
    t0 = time.time()
    r = httpx.post(f"{ROOT}/api/chat", json={"model": MODEL, "think": False, "stream": False, "keep_alive": "5m",
                                             "messages": [{"role": "user", "content": PROMPT}], "options": opts},
                   timeout=900).json()
    total = time.time() - t0
    ps = next((m for m in httpx.get(f"{ROOT}/api/ps").json()["models"] if m["name"].startswith(MODEL.split(":")[0])), {})
    gpu_share = ps.get("size_vram", 0) / max(ps.get("size", 1), 1)
    return {"ctx": ctx, "gpu": "CPU only" if num_gpu == 0 else f"{gpu_share:.0%} on GPU",
            "size_gb": round(ps.get("size", 0) / 2 ** 30, 2), "vram_gb": round(ps.get("size_vram", 0) / 2 ** 30, 2),
            "load_s": round(r.get("load_duration", 0) / 1e9, 1),
            "read_tok_s": round(r.get("prompt_eval_count", 0) / max(r.get("prompt_eval_duration", 1) / 1e9, 1e-9)),
            "write_tok_s": round(r.get("eval_count", 0) / max(r.get("eval_duration", 1) / 1e9, 1e-9), 1),
            "total_s": round(total, 1)}


print("HARDWARE:", hardware.summary())
print(f"\nAI ({MODEL})")
rows = [run(c) for c in (4096, 8192, 12288, 16384)]
rows.append(run(4096, num_gpu=0))
for r in rows:
    print(f"  ctx {r['ctx']:>5} | {r['gpu']:<12} | modelo {r['size_gb']} GB (VRAM {r['vram_gb']} GB) | "
          f"carregar {r['load_s']}s | lê {r['read_tok_s']} tok/s | escreve {r['write_tok_s']} tok/s | total {r['total_s']}s")
unload()

print("\nVOZ (Whisper, CPU int8)")
import numpy as np  # noqa: E402

try:
    import psutil  # optional

    proc = psutil.Process(os.getpid())
    rss = lambda: proc.memory_info().rss / 2 ** 20  # noqa: E731
except ImportError:
    rss = lambda: 0  # noqa: E731
from faster_whisper import WhisperModel  # noqa: E402

for size in ("base", "small"):
    m0, t0 = rss(), time.time()
    try:
        model = WhisperModel(size, device="cpu", compute_type="int8", local_files_only=True)
    except Exception as exc:
        print(f"  {size}: não baixado ({exc.__class__.__name__})")
        continue
    load = time.time() - t0
    audio = (np.sin(np.arange(16000 * 4) / 7) * 0.02).astype(np.float32)
    t0 = time.time()
    list(model.transcribe(audio, language="pt", beam_size=5)[0])
    print(f"  {size}: carregar {load:.1f}s | +{rss() - m0:.0f} MB RAM | 4 s de áudio em {time.time() - t0:.1f}s")
    del model
