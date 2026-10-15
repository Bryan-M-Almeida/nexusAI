"""Fast checks that need no AI server.   Run:  .venv\\Scripts\\python tests\\test_units.py"""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

from datetime import datetime, timedelta

import numpy as np

from nexus import assistant, control, knowledge, memory, tts
from nexus.db import db

failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name + (f"  ({detail})" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# -- conversation control detector (PT/EN/ES, with false-positive traps) --------------------------------
CASES = [
    ("Pausa", "pause"), ("Nexus, segura um pouquinho aí que eu vou atender a porta", "pause"),
    ("hold on, someone is at the door", "pause"), ("Espera un momento que me llaman", "pause"),
    ("pode continuar", "resume"), ("Repete por favor", "repeat"), ("O que você disse?", "repeat"),
    ("Não entendi", "clearer"), ("I didn't understand", "clearer"), ("Para de falar", "stop"), ("Para!", "stop"),
    ("para quem é a reunião de amanhã?", None), ("Continue a lista de compras com leite e pão", None),
    ("Um momento histórico foi a queda do muro de Berlim", None), ("Paraná fica no sul do Brasil", None),
    ("fale os valores exatos", None), ("E de uma mulher?", None),
]
for text, expected in CASES:
    got = control.detect(text)
    check(f"control.detect({text!r}) == {expected}", got == expected, f"got {got}")

# -- session-scoped history and action log (NX-LLM-019) -------------------------------------------------
old = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
db.execute("INSERT INTO messages(role, content, ts) VALUES ('user', 'Registra que gastei 42 reais', ?)", (old,))
db.execute("INSERT INTO actions(ts, kind, summary) VALUES (?, 'dados', 'Registrou em gastos: 42')", (old,))
memory.add_message("user", "Quanto pesa o coração em um homem adulto?")
memory.add_message("assistant", "Em média, cerca de 280 a 340 g.")
hist = memory.history(12)
check("history excludes previous sessions", all("gastei" not in m["content"] for m in hist), str(hist))
check("history keeps the current session", len(hist) == 2, str(hist))
context = assistant.build_context("fale os valores exatos")
check("context has no old action log", "gastos" not in context)

# -- knowledge: anatomy book and follow-up anchoring --------------------------------------------------------
knowledge.load_seed()
check("anatomy book indexed", any(d["category"] == "Anatomia" for d in knowledge.documents()))
check("follow-up 'E de uma mulher?' pulls the heart section",
      "Coração" in assistant.build_context("E de uma mulher?"))

# -- voice effect: no electrolarynx buzz, close to the dry voice (NX-VOZ-015) -----------------------------
t = np.arange(int(tts.RATE * 1.5)) / tts.RATE
dry = (0.3 * np.sin(2 * np.pi * 140 * t) * (1 + np.sin(2 * np.pi * 4 * t)) / 2).astype(np.float32)
wet = tts.apply_effect(dry, "jarvis")[: len(dry)]
fidelity = float(np.corrcoef(dry, wet)[0, 1])
f = np.fft.rfftfreq(len(dry), 1 / tts.RATE)


def buzz(sig):  # amplitude-modulation energy at 45 Hz, relative to the envelope's low-frequency energy
    s = np.abs(np.fft.rfft(sig * sig))
    return s[(f > 43) & (f < 47)].max() / s[(f > 1) & (f < 400)].mean()


ring_modulated = dry * (0.8 + 0.2 * np.sin(2 * np.pi * 45 * t))  # what the old v0.2/v0.3 effect did
check("jarvis effect keeps the voice (fidelity > 0.9)", fidelity > 0.9, f"{fidelity:.2f}")
check("jarvis effect has far less 45 Hz buzz than the old ring modulation",
      buzz(wet) < buzz(ring_modulated) / 10, f"new {buzz(wet):.3f} vs old {buzz(ring_modulated):.3f}")

# -- spoken name: NÉCSUS / NÉ-QUI-SÚS (NX-VOZ-016) ---------------------------------------------------------
check("name spoken as Nécsus (male voice)", tts.pronounce("Eu sou NEXUS. N.E.X.U.S online.", "pt", "male") == "Eu sou Nécsus. Nécsus online.")
check("name spoken as Néc-sus (female voice)", tts.pronounce("Eu sou NEXUS.", "pt", "female") == "Eu sou Néc-sus.")
check("name untouched in English", tts.pronounce("I am NEXUS.", "en") == "I am Nexus.")
check("other words untouched", tts.pronounce("nexusAI e annexus", "pt") == "nexusAI e annexus")

# -- emergency mode (NX-LLM-021) ---------------------------------------------------------------------------
from nexus import emergency  # noqa: E402

for text, expected in [("Preciso socorrer alguém agora", "general"), ("preciso fazer RCP, como faço?", "cpr"),
                       ("ele não está respirando", "cpr"), ("meu filho está engasgado", "choking"),
                       ("my dad is having a heart attack", "heart_attack"), ("mi hijo se está atragantando", "choking"),
                       ("queimei a mão no fogão", "burn"), ("acho que é um AVC", "stroke"),
                       ("Em que ano Maquiavel nasceu?", None), ("meu código está sangrando memória", None),
                       ("quero aprender sobre a queima de calorias", None)]:
    check(f"emergency.detect({text!r}) == {expected}", emergency.detect(text) == expected, str(emergency.detect(text)))
cpr = emergency.protocol_reply("cpr", "pt")
check("CPR protocol: lower half of the sternum, 192, never the xiphoid",
      "metade inferior do esterno" in cpr and "192" in cpr and "xif" not in cpr.lower())
check("CPR protocol in English and Spanish", "Cardiac arrest" in emergency.protocol_reply("cpr", "en")
      and "Parada cardiorrespiratoria" in emergency.protocol_reply("cpr", "es"))

# -- automatic memory: questions are not facts; same idea is not stored twice (NX-LLM-016) -----------------
for text, expected in [("preciso fazer RCP, como faço?", False), ("Quanto tempo uma pessoa dura em RCP?", False),
                       ("Eu tenho dois gatos, o Pixel e o Byte", True), ("Me llamo Lucía y vivo en Madrid", True)]:
    check(f"states_fact({text!r}) == {expected}", memory.states_fact(text) == expected)
check("similar: same fact in other words", memory.similar("O usuário tem dois gatos chamados Pixel e Byte", "Tem dois gatos: Pixel e Byte"))
check("similar: different facts sharing words", not memory.similar("Mora em São Paulo", "Trabalha em São Paulo"))
check("similar: a negation is a correction", not memory.similar("Gosta de café", "Não gosta de café"))

# -- calendar feed (ICS) import (v0.6) -----------------------------------------------------------------------
from nexus import integrations  # noqa: E402
from nexus.config import settings  # noqa: E402

tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
in_two = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
ICS = (f"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:a1@google.com\r\nDTSTART;TZID=America/Sao_Paulo:{tomorrow}T143000\r\n"
       f"DTEND;TZID=America/Sao_Paulo:{tomorrow}T153000\r\nSUMMARY:Reunião com o cliente\\, sala 2 com um título bem\r\n"
       f"  longo dobrado\r\nLOCATION:Sala 2\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:b2@google.com\r\n"
       f"DTSTART;VALUE=DATE:{in_two}\r\nSUMMARY:Feriado\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:c3@google.com\r\n"
       f"DTSTART:{tomorrow}T090000Z\r\nRRULE:FREQ=WEEKLY\r\nSUMMARY:Daily\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
parsed = integrations.parse_ics(ICS)
check("ICS: 3 events parsed, folded summary unfolded", len(parsed) == 3 and parsed[0]["summary"].endswith("título bem longo dobrado"),
      str(parsed[:1]))


class _Resp:
    def __init__(self, text): self.text = text


settings["calendar_ics_url"] = "https://example.invalid/basic.ics"
integrations._get = lambda url, **p: _Resp(ICS)
result = integrations.sync_calendar()
imported = db.all("SELECT title, start FROM events WHERE external_id LIKE 'ics:%' ORDER BY start")
check("ICS: imports single events, skips recurring", result.get("events") == 2 and result.get("recurring_skipped") == 1, str(result))
check("ICS: local time kept (14:30)", any(e["start"].endswith("14:30") for e in imported), str(imported))
integrations.sync_calendar()
check("ICS: re-sync does not duplicate", db.one("SELECT COUNT(*) n FROM events WHERE external_id LIKE 'ics:%'")["n"] == 2)
integrations._get = lambda url, **p: _Resp(ICS.replace("UID:b2@google.com", "UID:zz@google.com").replace("SUMMARY:Feriado", "SUMMARY:Outro"))
integrations.sync_calendar()
titles = [e["title"] for e in db.all("SELECT title FROM events WHERE external_id LIKE 'ics:%'")]
check("ICS: event deleted at the source disappears", "Feriado" not in titles and "Outro" in titles, str(titles))
settings["calendar_ics_url"] = ""

# -- temporary conversation and AI modes (v0.7) ---------------------------------------------------------------
saved_before = db.one("SELECT COUNT(*) n FROM messages")["n"]
memory.set_temporary(True)
memory.add_message("user", "conversa à toa")
memory.add_message("assistant", "resposta à toa")
check("temporary: nothing written to the database", db.one("SELECT COUNT(*) n FROM messages")["n"] == saved_before)
check("temporary: history comes from RAM", [m["content"] for m in memory.history(5)] == ["conversa à toa", "resposta à toa"])
check("temporary: repeat uses the temporary answer", assistant.last_reply() == "resposta à toa")
memory.set_temporary(False)
check("temporary: discarded when turned off", all("à toa" not in m["content"] for m in memory.history(50)))
settings["ai_mode"] = "direct"
check("direct mode instruction in the context", "MODE DIRECT" in assistant.build_context("O que é estoicismo?"))
settings["ai_mode"] = "assistant"
check("assistant mode adds no instruction", "MODE DIRECT" not in assistant.build_context("O que é estoicismo?"))

# -- voice pipeline and reports (v0.8) --------------------------------------------------------------------------
from nexus import i18n, tools, voice  # noqa: E402

for text in ("Nexus, que horas são", "Néxus abre a agenda", "Nécsus", "neksus", "Nexis ok", "next us please"):
    check(f"wake word heard in {text!r}", bool(voice.WAKE_RE.search(text)))
for text in ("o próximo passo", "anexo o arquivo", "nenhum problema"):
    check(f"no wake word in {text!r}", not voice.WAKE_RE.search(text))
det = voice.SpeechDetector()
check("VAD: Silero model loaded", det.session is not None)
rng = np.random.default_rng(1)
events = [det.feed((rng.standard_normal(voice.FRAME) * 0.01).astype(np.float32)) for _ in range(150)]
check("VAD: steady fan noise never opens a recording", not any(events), str(set(events)))
quiet = (np.sin(np.arange(16000) / 5) * 0.1).astype(np.float32)
check("gain: quiet speech normalized to ~0.5 peak", abs(np.abs(voice.normalize_audio(quiet)).max() - 0.5) < 0.01)
check("gain: silence is not amplified", np.abs(voice.normalize_audio(np.zeros(1600, np.float32))).max() == 0)
check("STT prompt carries NEXUS and the user name", "NEXUS" in voice.initial_prompt("Bryan") and "Bryan" in voice.initial_prompt("Bryan"))
check("clearer request quotes what the user said", "a piada" in i18n.t("clearer_request", said="não entendi a piada"))
check("report intent requires report_issue",
      assistant._needs_tool("Pronto!", False, "salve essa conversa para relatar erros", set()) is not None
      and assistant._needs_tool("Pronto!", True, "salve essa conversa para relatar erros", {"report_issue"}) is None)
from nexus import emergency  # noqa: E402

check("emergency: first-aid quiz is studying, not an emergency",
      emergency.detect("Me faça um simulado de 2 perguntas sobre primeiros socorros") is None)
check("emergency: study words + urgency still trigger", emergency.detect("estou estudando, meu amigo não respira agora") == "cpr")
knowledge.load_seed()
unsafe = "Não deixe em RCP por mais de 10 minutos sem ajuda; se não houver equipe, interrompa o procedimento."
check("CPR guard: 'stop after N minutes' replaced by the manual line",
      emergency.guard("cpr", unsafe, "pt").splitlines()[-1].startswith("Não pare até"))
safe = "Continue até a equipe chegar, revezando a cada 2 minutos, 100 a 120 compressões por minuto."
check("CPR guard: correct follow-up kept", emergency.guard("cpr", safe, "pt") == safe)
check("speech skips inline code / file paths", "report.md" not in voice.clean_for_speech("Envie `C:/r/report.md` à equipe."))
memory.add_message("user", "pergunta com erro")
rep = tools.report_issue("teste")
with open(rep["file"], encoding="utf-8") as f:
    report_text = f.read()
check("report file has the conversation", "pergunta com erro" in report_text and "## Conversation" in report_text)

# -- conversations (v0.9) ---------------------------------------------------------------------------------------
memory.new_conversation()
memory.add_message("user", "Quanto pesa o coração de um homem adulto?")
memory.add_message("assistant", "Entre 280 e 340 gramas.")
first = memory.current_conversation()
memory.new_conversation()
check("new conversation: history starts empty", memory.history(10) == [])
memory.add_message("user", "Qual a capital da Austrália?")
second = memory.current_conversation()
check("new conversation: only its own messages go to the model",
      [m["content"] for m in memory.history(10)] == ["Qual a capital da Austrália?"])
convs = {c["id"]: c for c in memory.conversations()}
check("conversation gets a provisional title from the first user message",
      convs[first]["title"].startswith("Quanto pesa o coração"), str(convs.get(first)))
memory.open_conversation(first)
check("reopened conversation brings its history back", memory.history(10)[-1]["content"] == "Entre 280 e 340 gramas.")
check("repeat uses the open conversation", assistant.last_reply() == "Entre 280 e 340 gramas.")
memory.set_conversation_title(first, "Peso do coração", "Valores médios por sexo.", final=True)
check("model title stored", db.one("SELECT title, titled_at FROM conversations WHERE id = ?", (first,))
      == {"title": "Peso do coração", "titled_at": -1})
tl = memory.timeline(50)
check("timeline is chronological across conversations", [m["id"] for m in tl] == sorted(m["id"] for m in tl)
      and {first, second} <= {m["conversation_id"] for m in tl})
db.execute("UPDATE conversations SET updated = ? WHERE id = ?",
           ((datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds"), first))
check("2 h of silence closes the open conversation", memory.current_conversation() is None)
memory.delete_conversation(second)
check("deleted conversation disappears with its messages",
      second not in {c["id"] for c in memory.conversations()}
      and db.one("SELECT COUNT(*) n FROM messages WHERE conversation_id = ?", (second,))["n"] == 0)

memory.new_conversation()
memory.add_message("assistant", "Olá, o que teremos para hoje?")  # opening greeting, never answered
greeting_only = memory.current_conversation()
memory.new_conversation()
memory.add_message("user", "oi")
check("greeting-only conversations are cleaned up",
      db.one("SELECT COUNT(*) n FROM messages WHERE content = 'Olá, o que teremos para hoje?'")["n"] == 0)  # ids are reused

# -- reminders with several lead times, quiet hours, briefing (v0.10) --------------------------------------------
from nexus import notify, scheduler  # noqa: E402
from nexus.config import settings as cfg  # noqa: E402

cfg["reminder_leads"] = "60,10,0"
fired = []
iso = lambda d: d.isoformat(timespec="minutes")  # noqa: E731
n = datetime.now()
db.execute("DELETE FROM events"); db.execute("DELETE FROM tasks"); db.execute("DELETE FROM reminders_sent")
ins = "INSERT INTO events(title, start, notes, remind_minutes, created) VALUES (?,?,?,?,?)"
db.execute(ins, ("Reunião antiga", iso(n + timedelta(minutes=30)), "", 10, iso(n - timedelta(hours=2))))
db.execute(ins, ("Criada agora", iso(n + timedelta(minutes=30)), "", 10, iso(n)))
db.execute(ins, ("Ontem", iso(n - timedelta(hours=20)), "", 10, iso(n - timedelta(days=2))))
db.execute(ins, ("beber água", iso(n - timedelta(minutes=1)), "reminder", 0, iso(n - timedelta(hours=1))))
scheduler._check(fired.append)
texts = {f["title"]: f["text"] for f in fired}
check("reminder: 1 h lead fires with the real time left",  # stored without seconds: 29 or 30
      any(f"{m} minutos" in texts.get("Reunião antiga", "") for m in (29, 30)), str(texts))
check("reminder: leads already past at creation don't fire", "Criada agora" not in texts, str(texts))
check("reminder: items from yesterday stay silent", "Ontem" not in texts, str(texts))
check("reminder: 'remind me to...' fires only at the time", texts.get("beber água", "").endswith("agora."), str(texts))
fired.clear(); scheduler._check(fired.append)
check("reminder: each lead fires once", fired == [], str(fired))
check("reminder leads parsed and sorted", scheduler.leads() == [60, 10, 0])
cfg["quiet_hours"] = "22:00-07:00"
check("quiet hours cross midnight", notify.in_quiet_hours(datetime(2026, 1, 1, 23, 30))
      and notify.in_quiet_hours(datetime(2026, 1, 1, 6, 59)) and not notify.in_quiet_hours(datetime(2026, 1, 1, 12, 0)))
cfg["quiet_hours"] = ""
check("no quiet hours by default", not notify.in_quiet_hours())
notify.clear(); notify.add("event", "Compromisso", "Lembrete: teste")
check("notification center stores and counts unread", notify.listing()["unread"] == 1)
notify.mark_read()
check("notification center: mark read", notify.listing()["unread"] == 0)
check("daily briefing mentions today's agenda", "compromisso" in scheduler.briefing_text().lower())
from nexus import llm  # noqa: E402
check("AI presets include local and cloud providers",
      {"ollama", "lmstudio", "openai", "anthropic", "gemini", "custom"} <= {x["id"] for x in llm.PRESETS})

# -- workspace (v0.11): path jail, undo, separate conversation, confirmed commands -------------------------------
from nexus import workspace  # noqa: E402

ws = workspace.create("App de Finanças", "um app em Python")
workspace.open_(ws["id"])
ws_conv = memory.enter_workspace(ws["id"], ws["conversation_id"])
check("workspace: folder created inside the data dir", workspace.root().is_dir() and "workspaces" in str(workspace.root()))
for bad in ("../fora.txt", "C:/Windows/x.txt", "/../../x", "sub/../../x.txt", ".nexus/notes.md", "~/x"):
    r = workspace.execute("write_file", {"path": bad, "content": "x"})
    check(f"workspace: path jail blocks {bad!r}", "error" in r, str(r))
r = workspace.execute("write_file", {"path": "src/main.py", "content": "print('v1')\n"})
check("workspace: creates files in subfolders", r.get("ok") and (workspace.root() / "src/main.py").exists(), str(r))
workspace.execute("edit_file", {"path": "src/main.py", "old_text": "v1", "new_text": "v2"})
check("workspace: edit_file replaces a unique snippet", "v2" in workspace.read_file("src/main.py")["content"])
check("workspace: edit_file refuses ambiguous snippets",
      "error" in workspace.execute("edit_file", {"path": "src/main.py", "old_text": "zzz", "new_text": "y"}))
workspace.undo()
check("workspace: undo restores the previous version", "v1" in workspace.read_file("src/main.py")["content"])
workspace.undo()
check("workspace: undo of a created file removes it", not (workspace.root() / "src/main.py").exists())
asked = []
r = workspace.execute("run_command", {"command": "echo ola"}, ask=lambda c: asked.append(c) or False)
check("workspace: commands need confirmation (denied = not run)", r.get("denied") and asked == ["echo ola"], str(r))
r = workspace.execute("run_command", {"command": "echo ola"}, ask=lambda c: True)
check("workspace: confirmed command runs in the workspace", r.get("exit_code") == 0 and "ola" in r.get("stdout", ""), str(r))
memory.add_message("user", "crie o main.py")
check("workspace: its conversation is not listed with normal ones", ws_conv not in {c["id"] for c in memory.conversations()})
check("workspace: nor in the timeline", all(m["conversation_id"] != ws_conv for m in memory.timeline(500)))
check("workspace: context has the files, not the user's memories",
      "Workspace files" in assistant.build_context("oi") and "remember about the user" not in assistant.build_context("oi"))
check("workspace: file tools offered, personal tools not",
      {"write_file", "run_command"} <= {x["function"]["name"] for x in assistant.turn_tools()}
      and "record_data" not in {x["function"]["name"] for x in assistant.turn_tools()})
check("workspace: 'I'll fix it' without acting is sent back to the model",
      assistant._needs_file_tool("O erro ocorre no import. Vou corrigir isso.", True) is not None
      and assistant._needs_file_tool("Pronto: corrigi o import em test_calc.py.", True) is None)
memory.leave_workspace(); workspace.close()
check("workspace: leaving restores normal tools", "record_data" in {x["function"]["name"] for x in assistant.turn_tools()})
workspace.delete(ws["id"])
check("workspace: delete moves the folder to .trash", any((workspace.ROOT / ".trash").iterdir()))

# migration of pre-v0.9 messages: a 2 h gap splits them into two conversations
import sqlite3  # noqa: E402
import tempfile  # noqa: E402
from nexus.db import DB  # noqa: E402

old_db = tempfile.mktemp(suffix=".db")
con = sqlite3.connect(old_db)
con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL)")
con.executemany("INSERT INTO messages(role, content, ts) VALUES (?,?,?)", [
    ("user", "oi", "2026-10-13T09:00:00"), ("assistant", "olá", "2026-10-13T09:00:05"),
    ("user", "e o clima?", "2026-10-13T15:00:00"), ("assistant", "sol", "2026-10-13T15:00:04")])
con.commit(); con.close()
migrated = DB(old_db)
groups = migrated.all("SELECT conversation_id, COUNT(*) n FROM messages GROUP BY conversation_id")
check("migration: old messages split by 2 h gaps", [g["n"] for g in groups] == [2, 2], str(groups))
check("migration: titles from the first user message",
      [c["title"] for c in migrated.all("SELECT title FROM conversations ORDER BY id")] == ["oi", "e o clima?"])
migrated.conn.close()

print(f"\n{len(failures)} failure(s)")
raise SystemExit(1 if failures else 0)
