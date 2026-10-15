"""Long conversation: time Ollama spends READING the prompt per answer (cache misses show up here; its token
count always reports the whole prompt, cached or not) and total time per answer, with the history window
sliding one message per turn (v0.15.0 behaviour) vs anchored and jumping (v0.15.1).
Run: .venv\\Scripts\\python tests\\bench_long_conversation.py   (several minutes)"""
import _isolated  # noqa: F401

import time

from nexus import assistant, knowledge, llm, memory
from nexus.config import settings

knowledge.load_seed()
_isolated.load_example_profile()
settings["auto_title"] = False   # isolate the history effect
settings["auto_memory"] = False
QUESTIONS = ["O que é juros compostos?", "E juros simples?", "Qual a diferença prática?", "Me dá um exemplo com 1000 reais.",
             "E em 10 anos?", "O que é inflação?", "Como ela afeta a poupança?", "O que é CDI?", "E Selic?",
             "Qual rende mais hoje, em geral?", "O que é reserva de emergência?", "Quanto guardar?",
             "Onde deixar essa reserva?", "E tesouro direto?", "Resume tudo em 3 frases.", "Obrigado!"]


def run(sliding: bool):
    memory.new_conversation()
    brain = assistant.Assistant(lambda e, p: None)
    processed, times = [], []
    for q in QUESTIONS:
        if sliding:
            assistant._anchors.clear()  # old behaviour: the window re-slides every turn
            settings["history_turns"] = 12
        t0 = time.time()
        brain.ask(q)
        times.append(time.time() - t0)
        processed.append((llm.calls_log[0].get("prompt_eval_duration") or 0) / 1e9 if llm.calls_log else 0)
        llm.calls_log.clear()
    return processed, times


for label, sliding in (("deslizante (v0.15.0)", True), ("ancorada (v0.15.1)", False)):
    processed, times = run(sliding)
    late = slice(8, None)  # once the window is full
    print(f"{label:<22} leitura do prompt/resposta (a partir da 9ª): {sum(processed[late]) / len(processed[late]):.2f}s | "
          f"tempo médio total {sum(times) / len(times):.1f}s | a partir da 9ª {sum(times[late]) / len(times[late]):.1f}s")
    print("   leitura/total:", [f"{p:.1f}/{t:.0f}s" for p, t in zip(processed, times)])
