"""Where do the extra ~2 s per request go?   Run: .venv\\Scripts\\python tests\\bench_overhead.py"""
import _isolated  # noqa: F401

import time

import httpx

from nexus import assistant, knowledge, llm, tools

knowledge.load_seed()
_isolated.load_example_profile()
assistant.warm_up()

t0 = time.time()
ctx = assistant.build_context("Qual é a capital da Austrália?")
system = assistant.build_system()
print(f"montar contexto+sistema (Python): {time.time() - t0:.3f}s")

for with_tools in (True, False):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": f"<context>\n{ctx}\n</context>\n\nQual é a capital da Austrália?"}]
    body = llm._native_body(messages, tools.SCHEMAS if with_tools else None, 0.3)
    for i in range(2):
        t0 = time.time(); first = None
        with httpx.stream("POST", f"{llm._ollama_root()}/api/chat", json=body, timeout=300) as r:
            for line in r.iter_lines():
                if first is None and line.strip():
                    first = time.time() - t0
                if '"done":true' in line:
                    import json
                    d = json.loads(line)
        wall = time.time() - t0
        print(f"ferramentas={with_tools!s:<5} rodada {i}: 1º byte {first:5.2f}s | parede {wall:5.2f}s | "
              f"Ollama total {d['total_duration'] / 1e9:5.2f}s (prompt {d['prompt_eval_duration'] / 1e9:4.2f}s, "
              f"geração {d['eval_duration'] / 1e9:4.2f}s, load {d['load_duration'] / 1e9:4.2f}s)")
