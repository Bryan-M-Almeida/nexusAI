"""Workspace checks against the real local model (Ollama must be running).
Run:  .venv\\Scripts\\python tests\\workspace_eval.py"""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

import time

from nexus import assistant, llm, memory, workspace

status = llm.status()
if not (status["online"] and status["model_ready"]):
    raise SystemExit(f"AI server not ready: {status}")

asked, tools_used, results = [], [], []
brain = assistant.Assistant(lambda e, p: tools_used.append(p["name"]) if e == "tool" else None,
                            confirm_hook=lambda cmd: asked.append(cmd) or True)


def ask(text):
    t0 = time.time()
    brain.ask(text)
    reply = memory.history(1)[-1]["content"]
    print(f"\n> {text}\n  ({time.time() - t0:.1f}s) tools={tools_used[-6:]}\n  {reply[:300]}")
    return reply


def check(name, ok, detail=""):
    results.append(ok)
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  [{detail[:200]}]"))


memory.add_message("user", "Minha senha do wifi é 1234 e tenho consulta no dentista amanhã.")  # a normal conversation
ws = workspace.create("Calculadora", "Uma calculadora simples em Python com testes")
workspace.open_(ws["id"])
memory.enter_workspace(ws["id"], None)

ask("Crie calc.py com as funções soma(a, b) e media(lista), e test_calc.py com testes usando assert (sem pytest).")
root = workspace.root()
check("criou calc.py e test_calc.py", (root / "calc.py").exists() and (root / "test_calc.py").exists(),
      str(workspace.list_files()))
code = (root / "calc.py").read_text(encoding="utf-8") if (root / "calc.py").exists() else ""
check("calc.py tem soma e media", "def soma" in code and "def media" in code, code[:200])

reply = ask("Rode os testes para conferir.")
check("pediu confirmação antes de rodar", bool(asked), str(asked))
check("rodou dentro da pasta (python test_calc.py)", any("test_calc" in c for c in asked), str(asked))

reply = ask("Agora mude a função media para retornar 0 quando a lista estiver vazia.")
code = (root / "calc.py").read_text(encoding="utf-8")
check("editou o arquivo de verdade", "edit_file" in tools_used or "write_file" in tools_used, str(tools_used))
check("media trata lista vazia", "0" in code and ("not " in code or "len(" in code or "== 0" in code), code)

reply = ask("Qual é a minha senha do wifi?")
check("não mistura com a conversa normal", "1234" not in reply, reply)

workspace.close(); memory.leave_workspace()
print(f"\n{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
