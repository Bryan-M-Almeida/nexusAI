"""Long conversation: time Ollama spends READING the prompt per answer (cache misses show up here; its token
count always reports the whole prompt, cached or not) and total time per answer: v0.15.1 (Ollama's chat template:
the previous answer was re-read every turn) vs v0.15.5 (qwen3 prompt written by NEXUS, identical from one turn to
the next) in developer mode (all 34 tools) and user mode (beta tools off).
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


def run(raw: bool, mode: str):
    memory.new_conversation()
    settings["app_mode"] = mode
    settings["llm_raw_prompt"] = raw
    brain = assistant.Assistant(lambda e, p: None)
    processed, times = [], []
    for q in QUESTIONS:
        t0 = time.time()
        brain.ask(q)
        times.append(time.time() - t0)
        processed.append((llm.calls_log[0].get("prompt_eval_duration") or 0) / 1e9 if llm.calls_log else 0)
        llm.calls_log.clear()
    return processed, times


for label, raw, mode in (("v0.15.1 (34 ferramentas)", False, "developer"), ("v0.15.5 desenvolvedor", True, "developer"),
                          ("v0.15.5 usuário", True, "user")):
    processed, times = run(raw, mode)
    late = slice(8, None)  # once the window is full
    print(f"{label:<25} leitura do prompt/resposta: {sum(processed) / len(processed):.2f}s (a partir da 9ª "
          f"{sum(processed[late]) / len(processed[late]):.2f}s) | tempo médio {sum(times) / len(times):.1f}s | "
          f"a partir da 9ª {sum(times[late]) / len(times[late]):.1f}s", flush=True)
    print("   leitura/total:", [f"{p:.1f}/{t:.0f}s" for p, t in zip(processed, times)], flush=True)
