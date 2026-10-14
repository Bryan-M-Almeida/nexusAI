"""Prompt-processing speed vs num_batch on this GPU.   Run: .venv\\Scripts\\python tests\\bench_batch.py"""
import _isolated  # noqa: F401

import time

import httpx

from nexus import llm
from nexus.config import settings

root = llm._ollama_root()
text = "O NEXUS é um assistente pessoal local. " * 120  # ~1000 tokens of fresh text
for num_batch in (512, 1024, 2048):
    httpx.post(f"{root}/api/generate", json={"model": settings["llm_model"], "keep_alive": 0}, timeout=60)  # unload
    time.sleep(2)
    speeds = []
    for i in range(2):  # 1st run includes load; 2nd run measures processing only
        body = {"model": settings["llm_model"], "prompt": f"[{num_batch}-{i}-{time.time()}] {text}", "stream": False,
                "think": False, "options": {"num_ctx": 8192, "num_batch": num_batch, "num_predict": 1}}
        r = httpx.post(f"{root}/api/generate", json=body, timeout=300).json()
        speeds.append(r["prompt_eval_count"] / (r["prompt_eval_duration"] / 1e9))
    print(f"num_batch={num_batch:5}: {speeds[1]:6.0f} tokens/s de processamento de prompt")
