"""How much of the prompt does Ollama re-process between turns?   Run: .venv\\Scripts\\python tests\\bench_cache.py"""
import _isolated  # noqa: F401

from nexus import assistant, knowledge, llm, tools

knowledge.load_seed()
_isolated.load_example_profile()
system = {"role": "system", "content": assistant.build_system()}


def call(label, messages):
    llm.calls_log.clear()
    for _ in llm.stream_chat(messages, tools.SCHEMAS):
        pass
    c = llm.calls_log[-1]
    print(f"{label:<58} prompt {c['prompt_eval_count']:5} tok | {c['prompt_eval_duration'] / 1e9:5.2f}s")


filler = "Contexto extra. " * 60  # ~300 tokens of new text
call("A) frio: sistema + ferramentas + pergunta", [system, {"role": "user", "content": "Oi"}])
call("B) idêntico a A", [system, {"role": "user", "content": "Oi"}])
call("C) A + resposta + nova pergunta curta", [system, {"role": "user", "content": "Oi"},
     {"role": "assistant", "content": "Olá! Como posso ajudar?"}, {"role": "user", "content": "Tudo bem?"}])
call("D) C + ~300 tokens novos no fim", [system, {"role": "user", "content": "Oi"},
     {"role": "assistant", "content": "Olá! Como posso ajudar?"}, {"role": "user", "content": "Tudo bem? " + filler}])
call("E) mesmo histórico, mas 1ª mensagem mudou (cache quebra cedo)", [system, {"role": "user", "content": "Oi!!"},
     {"role": "assistant", "content": "Olá! Como posso ajudar?"}, {"role": "user", "content": "Tudo bem? " + filler}])
