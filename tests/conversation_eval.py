"""End-to-end conversation checks against the real local model (Ollama must be running).
Run:  .venv\\Scripts\\python tests\\conversation_eval.py        (takes a few minutes)"""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

import re
import time
from datetime import datetime, timedelta

from nexus import assistant, knowledge, llm, memory, tools
from nexus.config import settings
from nexus.db import db

settings["auto_memory"] = False
knowledge.load_seed()
_isolated.load_example_profile()
status = llm.status()
if not (status["online"] and status["model_ready"]):
    raise SystemExit(f"AI server not ready: {status}")

brain = assistant.Assistant(lambda event, payload: None)
results = []


def ask(text):
    t0 = time.time()
    brain.ask(text)
    reply = memory.history(1)[-1]["content"] if memory.history(1) else ""
    print(f"\n> {text}\n  ({time.time() - t0:.1f}s) {reply[:220]}")
    return reply


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  [{detail[:160]}]"))


# 1) Regression of the 2026-10-13 conversation (NX-LLM-019 / NX-LLM-020): an old session about expenses
#    must not leak into an ambiguous follow-up.
old = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
for role, content in [("user", "Registra que gastei 42 reais no mercado e 18 no almoço."),
                      ("assistant", "Registrei os gastos: R$ 42,00 no mercado e R$ 18,00 no almoço.")]:
    db.execute("INSERT INTO messages(role, content, ts) VALUES (?,?,?)", (role, content, old))
db.execute("INSERT INTO actions(ts, kind, summary) VALUES (?, 'dados', ?)", (old, "Registrou em 'gastos': 42 mercado"))

man = ask("Quanto pesa o coração em um homem adulto?")
check("homem: valores em gramas", bool(re.search(r"\d{3}\s*(g|gramas)", man)), man)
woman = ask("E de uma mulher?")
check("mulher: valores em gramas", bool(re.search(r"\d{3}\s*(g|gramas)", woman)), woman)
check("mulher: não repete a faixa do homem", "250 gramas e 350" not in woman and "250 e 350" not in woman, woman)
exact = ask("fale os valores exatos")
check("'valores exatos' fala do coração, não de gastos", "R$" not in exact and "gast" not in exact.lower(), exact)
check("'valores exatos' explica que não há valor exato ou dá médias",
      bool(re.search(r"(não (há|existe)|varia|média|aproximad)", exact.lower())), exact)

# 2) Tools: actions must really be stored (NX-LLM-003)
ask("Me lembra de ligar para o dentista amanhã às 10h.")
tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
check("lembrete criado para amanhã 10:00", any(e["start"] == f"{tomorrow}T10:00" for e in tools.list_events(
    datetime.now().isoformat(timespec="minutes"), (datetime.now() + timedelta(days=2)).isoformat(timespec="minutes"))))
ask("Registra que gastei 30 reais em livros.")
check("gasto registrado", any(r.get("amount") in (30, 30.0, "30") for r in tools.query_data("gastos")) or
      any(tools.query_data(c["collection"]) for c in tools.list_collections()))
ask("Lembra que eu prefiro reuniões de manhã.")
check("memória salva", any("manh" in m["content"].lower() for m in memory.all_memories()))
ask("Aprenda que o wifi do escritório se chama NEXUS-LAB.")
check("conhecimento aprendido", any(d["source"].startswith("learned:") for d in knowledge.documents()))

# 3) Languages
en = ask("What do the Stoics say about things outside our control? One sentence.")
check("responde em inglês", bool(re.search(r"\b(the|control|what)\b", en.lower())) and " não " not in en, en)

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
raise SystemExit(0 if passed == len(results) else 1)
