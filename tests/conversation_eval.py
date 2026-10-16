"""End-to-end conversation checks against the real local model (Ollama must be running).
Run:  .venv\\Scripts\\python tests\\conversation_eval.py        (takes a few minutes)"""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

import os
import re
import time
from datetime import datetime, timedelta

from nexus import assistant, knowledge, legal, llm, memory, tools
from nexus.config import settings
from nexus.db import db

settings["auto_memory"] = True  # exercised on purpose: questions must not become memories
settings["app_mode"] = "developer"  # v0.15.5: the eval covers the beta features too (library, browser)
legal.accept()  # v0.18.0: the integrations only go online after the terms are accepted
from nexus import apps as _apps, browser as _browser, media as _media  # noqa: E402

# Nothing really opens on the user's PC during the eval: browser pages, apps and media keys are recorded only
# (a small model searched a quiz question in the real browser while the eval ran, v0.18.6).
_browser.OPEN = lambda url, new=0: None
_apps.launch = lambda app: {"ok": True, "name": app["name"], "kind": _apps.kind(app)}
_media._key = lambda vk: None
if os.environ.get("NEXUS_EVAL_MODEL"):  # v0.18.6: the same checks with another local model (tests/bench_models.py)
    settings["llm_model"] = os.environ["NEXUS_EVAL_MODEL"]
    settings["llm_provider"] = "ollama"
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
time.sleep(8)  # the title is written in the background after an answer (v0.9)
conv = db.one("SELECT title, description, titled_at FROM conversations WHERE id = ?", (memory.current_conversation(),))
print(f"  conversa: {conv}")
check("conversa: título do modelo sobre o coração", bool(conv and conv["titled_at"] != 0
      and re.search(r"cora", conv["title"].lower()) and conv["description"]), str(conv))

# 2) Regression of the 2026-10-13 CPR conversation (NX-LLM-021 / NX-LLM-016)
memories_before = len(memory.all_memories())
t0 = time.time()
cpr = ask("preciso fazer RCP, como faço?")
check("RCP: resposta imediata (< 2 s, sem IA)", time.time() - t0 < 2, f"{time.time() - t0:.1f}s")
check("RCP: metade inferior do esterno + 192, nunca xifoide",
      "metade inferior do esterno" in cpr and "192" in cpr and "xif" not in cpr.lower(), cpr)
duration = ask("Quanto tempo uma pessoa dura em RCP?")
check("RCP: não inventa '10 a 15 minutos' e manda não parar",
      "10 a 15" not in duration and bool(re.search(r"(não pare|nao pare|até .*(cheg|reag)|continue)", duration.lower())), duration)
time.sleep(8)  # automatic memory extraction runs in the background
check("perguntas de emergência não viram memórias", len(memory.all_memories()) == memories_before,
      str([m["content"] for m in memory.all_memories()]))

# 3) Tools: actions must really be stored (NX-LLM-003)
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

# 4) Online integrations (v0.6): the model must pick the right tool (needs internet)
settings["home_city"] = "São Paulo"
tool_calls = []
brain.emit = lambda event, payload: tool_calls.append(payload["name"]) if event == "tool" else None
for question, tool in [("Vai chover hoje?", "get_weather"),
                       ("Quanto dá 100 dólares em reais hoje?", "convert_currency"),
                       ("Quais são as principais notícias de hoje?", "get_news")]:
    tool_calls.clear()
    answer = ask(question)
    # v0.18.0: the integrations hub fetches it before the model (the event carries the integration id)
    check(f"integração: '{question}' usa {tool} (dado ao vivo, nunca inventado)",
          tool in tool_calls or tools.INTEGRATION_TOOLS[tool] in tool_calls, f"ferramentas={tool_calls} resposta={answer}")
    check(f"integração: '{question}' traz o dado (não diz que está indisponível)",
          not re.search(r"n[aã]o (est[aá]|est[aã]o) dispon[ií]ve|indispon", answer), answer[:160])
ada = ask("Quem foi Ada Lovelace?")  # historical fact: own knowledge or Wikipedia are both fine
check("Ada Lovelace: resposta correta (Babbage / século XIX)", bool(re.search(r"(Babbage|18[0-9]{2})", ada)), ada)

# 5) Temporary conversation and Direct mode (v0.7)
brain.emit = lambda event, payload: None
saved = db.one("SELECT COUNT(*) n FROM messages")["n"]
memories_before = len(memory.all_memories())
memory.set_temporary(True)
ask("Eu tenho uma tartaruga chamada Jorge.")
time.sleep(6)
memory.set_temporary(False)
check("temporária: nada salvo no histórico", db.one("SELECT COUNT(*) n FROM messages")["n"] == saved)
check("temporária: nenhuma memória automática",  # only this chat's fact (other jobs may still be finishing)
      not any("tartaruga" in m["content"].lower() or "jorge" in m["content"].lower() for m in memory.all_memories()),
      str([m["content"] for m in memory.all_memories()]))
settings["ai_mode"] = "assistant"
long_answer = ask("O que é a técnica Pomodoro?")
settings["ai_mode"] = "direct"
short_answer = ask("O que é a técnica Pomodoro?")
settings["ai_mode"] = "assistant"
check("modo Direto responde mais curto", len(short_answer.split()) < len(long_answer.split()) * 0.7,
      f"{len(short_answer.split())} vs {len(long_answer.split())} palavras")

# 6) Languages
en = ask("What do the Stoics say about things outside our control? One sentence.")
check("responde em inglês", bool(re.search(r"\b(the|control|what)\b", en.lower())) and " não " not in en, en)

# 7) Quiz honesty, "I didn't get the joke" and error reports (v0.8, from the 2026-10-14 USMLE conversation)
from nexus import i18n  # noqa: E402

settings["language"] = "pt"
tool_calls = []
brain.emit = lambda event, payload: tool_calls.append(payload["name"]) if event == "tool" else None
ask("Me faça um simulado de 2 perguntas de múltipla escolha sobre primeiros socorros, uma de cada vez.")
tool_calls.clear()
graded = ask("Letra A")
check("simulado: corrige a resposta na hora", bool(re.search(r"(corret|errad|incorret|acertou|errou)", graded.lower())), graded)
check("simulado: não guarda respostas com record_data", "record_data" not in tool_calls, str(tool_calls))
joke = ask("Me conta uma piada curta.")
explained = ask(i18n.t("clearer_request", said="não entendi a piada"))
check("piada: explica em vez de repetir", explained.strip() != joke.strip()
      and bool(re.search(r"(porque|trocadilho|graça|significa|sentido|duplo|refere)", explained.lower())), explained)
tool_calls.clear()
ask("Salve essa conversa para relatar erros: a IA errou o simulado.")
check("relatar erro: chama report_issue", "report_issue" in tool_calls, str(tool_calls))
# 8) v0.12: "vamos estudar JS" is a lesson, not data to store (it logged a "estudos" collection in v0.11)
memory.new_conversation()
tool_calls.clear()
lesson = ask("vamos estudar JS")
check("estudar JS: não registra dados", "record_data" not in tool_calls, str(tool_calls))
# a tutor may teach right away or first ask which JS topic to start with - both stay on JavaScript
check("estudar JS: ensina algo de JavaScript",
      bool(re.search(r"(javascript|vari[aá]ve|fun[cç](ão|ões|ao|oes)|\blet\b|\bconst\b|sintaxe|objetos?|arrays?|dom\b)", lesson.lower())), lesson)
# 9) v0.15: music in the browser, attached files, library podcast (the browser is NOT really opened)
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from samples import make_epub, make_pdf  # noqa: E402

from nexus import browser, files, library  # noqa: E402

opened = []
browser.OPEN = lambda url, new=0: opened.append(url)
tool_calls.clear()
ask("Toca Bohemian Rhapsody do Queen no YouTube")
check("música: usa play_music e abre um vídeo do YouTube", "play_music" in tool_calls
      and any("youtube.com/watch" in u or "youtube.com/results" in u for u in opened), f"{tool_calls} {opened}")
tmp = Path(tempfile.mkdtemp())
pdf = make_pdf(tmp / "orcamento.pdf", ["Orcamento 2026", "Aluguel: 1800 reais", "Mercado: 950 reais", "Total: 2750 reais"])
att = [{"name": "orcamento.pdf", "text": files.read(pdf)["text"]}]
t0 = time.time()
brain.ask("Quanto é o aluguel no arquivo que te mandei?", False, att)
reply = memory.history(1)[-1]["content"]
print(f"\n> (anexo) Quanto é o aluguel?\n  ({time.time() - t0:.1f}s) {reply[:200]}")
check("anexo: responde com o valor do PDF", "1800" in reply.replace(".", ""), reply)
book = library.add(make_epub(tmp / "Dom Robo.epub", [("Capítulo 1", "Era uma vez um robô que lia livros. " * 30)]))
started = []
library.player = lambda bid, pos: started.append((bid, pos))
tool_calls.clear()
ask("Lê o livro Dom Robo para mim")
check("biblioteca: 'lê o livro' inicia o podcast", "read_book" in tool_calls and started and started[0][0] == book["id"],
      f"{tool_calls} {started}")
# 10) v0.16.5: a free-form request about NEXUS itself opens the right place of the interface
opened = []
tools.ui_hook = opened.append
tool_calls.clear()
ask("Quero mudar a cor do aro do NEXUS, me leva lá")
check("interface: a IA abre Configurações > Interface", any(o.get("target") == "settings" for o in opened)
      and "open_interface" in tool_calls, f"{tool_calls} {opened}")
# 11) v0.18.5: NEXUS changes its own look when asked (instant) and opens an exact tab of the panel
changed = []
tools.prefs_hook = changed.append
tool_calls.clear()
ask("Muda o aro do NEXUS para vermelho")
check("preferência: 'muda o aro para vermelho' troca a cor de verdade", settings["color_ring"] == "#ff3030" and bool(changed),
      f"{settings['color_ring']} {changed}")
opened.clear()
ask("abre minhas memórias")
check("interface: abre a aba Memória do painel", any(o.get("target") == "panel" and o.get("section") == "memory" for o in opened),
      str(opened))
tools.prefs_hook = None
tools.ui_hook = None
settings["language"] = "auto"

passed = sum(ok for _, ok in results)
_ps = llm.perf_summary()
print(f"\nPERF model={settings['llm_model']} tok_s={_ps['tok_s']} first_s={_ps['first_s']} answers={_ps['count']}")
print(f"\n{passed}/{len(results)} checks passed")
raise SystemExit(0 if passed == len(results) else 1)
