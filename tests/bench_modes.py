"""Assistant vs Direct mode: length and time of the same answers.   Run: .venv\\Scripts\\python tests\\bench_modes.py"""
import _isolated  # noqa: F401

import time

from nexus import assistant, knowledge, memory
from nexus.config import settings

knowledge.load_seed()
_isolated.load_example_profile()
settings["auto_memory"] = False
assistant.warm_up()
QUESTIONS = ["O que é estoicismo?", "Como funciona juros compostos?", "Qual a diferença entre RAM e SSD?",
             "Me dá uma dica para dormir melhor."]
results = {}
for mode in ("assistant", "direct"):
    settings["ai_mode"] = mode
    memory.set_temporary(True)  # each mode starts from a clean, unsaved conversation
    brain = assistant.Assistant(lambda e, p: None)
    rows = []
    for q in QUESTIONS:
        t0 = time.time()
        brain.ask(q)
        reply = memory.history(1)[-1]["content"]
        rows.append((time.time() - t0, len(reply.split())))
        print(f"[{mode:<9}] {rows[-1][0]:5.1f}s {rows[-1][1]:4} palavras | {q} -> {reply[:110]!r}")
    results[mode] = rows
for mode, rows in results.items():
    print(f"{mode:<9}: média {sum(r[0] for r in rows) / len(rows):.1f}s, {sum(r[1] for r in rows) / len(rows):.0f} palavras")
