"""Latency benchmark against the real model.   Run:  .venv\\Scripts\\python tests\\bench_latency.py
Measures, per message: time to first token (what the user waits before NEXUS starts answering) and total time.
Starts with the model unloaded, like opening the app."""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

import sys
import time

import httpx

from nexus import assistant, knowledge, llm
from nexus.config import settings

knowledge.load_seed()
_isolated.load_example_profile()
settings["auto_memory"] = True
settings["home_city"] = "São Paulo"

root = llm._ollama_root()
httpx.post(f"{root}/api/generate", json={"model": settings["llm_model"], "keep_alive": 0}, timeout=60)  # unload
time.sleep(2)

warm = "--warm" in sys.argv
if warm and hasattr(assistant, "warm_up"):
    t0 = time.time()
    assistant.warm_up()
    print(f"warm-up (during the boot animation): {time.time() - t0:.1f}s")

marks = {}


def on_event(event, payload):
    if event == "token" and "first" not in marks:
        marks["first"] = time.time()


brain = assistant.Assistant(on_event)
SCRIPT = [
    "Oi! Tudo bem?",
    "Me lembra de beber água daqui a uma hora.",
    "Eu tenho dois gatos, o Pixel e o Byte.",
    "Quanto pesa o coração de um homem adulto?",
    "E de uma mulher?",
    "Qual é a capital da Austrália?",
    "Vai chover hoje?",
    "Quais são as principais notícias de hoje?",
    "What do the Stoics say about things outside our control? One sentence.",
]
rows = []
for text in SCRIPT:
    marks.clear()
    t0 = time.time()
    brain.ask(text)
    total = time.time() - t0
    ttft = marks.get("first", time.time()) - t0
    rows.append((text, ttft, total))
    print(f"{ttft:6.1f}s até a 1ª palavra | {total:6.1f}s total | {text}")
    if "-v" in sys.argv:
        for c in llm.calls_log:
            s = lambda k: (c.get(k) or 0) / 1e9
            print(f"        chamada: load {s('load_duration'):5.1f}s | prompt {c.get('prompt_eval_count')} tok em "
                  f"{s('prompt_eval_duration'):5.1f}s | geração {c.get('eval_count')} tok em {s('eval_duration'):4.1f}s")
    llm.calls_log.clear()
    time.sleep(1.5)  # user reading / typing
print(f"\nmédia: {sum(r[1] for r in rows) / len(rows):.1f}s até a 1ª palavra, {sum(r[2] for r in rows) / len(rows):.1f}s total"
      f" | 1ª mensagem: {rows[0][1]:.1f}s")
