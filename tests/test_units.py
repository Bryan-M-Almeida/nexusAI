"""Fast checks that need no AI server.   Run:  .venv\\Scripts\\python tests\\test_units.py"""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

import json
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

# -- v0.12: a real answer written before a tool call is kept (not wiped from the screen) -------------------------
from nexus import llm as _llm  # noqa: E402

LESSON = "JavaScript é a linguagem da web. Vamos começar por variáveis: let, const e var, e depois funções. " * 2
script = iter([[("token", LESSON), ("tool_calls", [{"id": "c1", "name": "get_datetime", "arguments": "{}"}])],
               [("token", "Quer começar por variáveis?"), ("done", None)]])
real_stream = _llm.stream_chat
_llm.stream_chat = lambda *a, **k: iter(next(script))
seen = []
brain = assistant.Assistant(lambda e, p: seen.append((e, p)))
memory.new_conversation()
brain.ask("vamos estudar JS")
_llm.stream_chat = real_stream
final = memory.history(1)[-1]["content"]
check("long answer before a tool call stays in the saved reply", LESSON.strip() in final and final.endswith("variáveis?"), final)
check("...and is not wiped from the screen (no reset)", not any(e == "reset" for e, _ in seen), str([e for e, _ in seen]))
script = iter([[("token", "Vou verificar."), ("tool_calls", [{"id": "c2", "name": "get_datetime", "arguments": "{}"}])],
               [("token", "São 10h."), ("done", None)]])
_llm.stream_chat = lambda *a, **k: iter(next(script))
seen.clear(); brain.ask("que horas são?")
_llm.stream_chat = real_stream
check("short narration before a tool call is still removed",
      any(e == "reset" for e, _ in seen) and memory.history(1)[-1]["content"] == "São 10h.", memory.history(1)[-1]["content"])

# -- v0.12: connection modes, performance profiles, hardware fit ------------------------------------------------
from nexus import hardware, performance  # noqa: E402

cfg["network_mode"] = "offline"
check("offline: online tools refuse without touching the network", "offline" in str(tools.execute("get_weather", {})))
cfg["llm_base_url"], saved_url = "https://api.openai.com/v1", cfg["llm_base_url"]
check("offline: a cloud AI server is never contacted", _llm.status().get("offline_mode") is True)
try:
    list(_llm.stream_chat([{"role": "user", "content": "oi"}]))
    blocked = False
except _llm.LLMOffline:
    blocked = True
check("offline: chat with a cloud provider is blocked", blocked)
cfg["llm_base_url"] = saved_url
check("offline: local AI (Ollama) is still allowed", not _llm.offline_blocked())
cfg["network_mode"] = "hybrid"
check("live-data nudge only outside offline mode",
      assistant._needs_tool("", False, "vai chover hoje?", set()) is not None)
check("VRAM fit uses the measured table (8 GB -> 8192, 12 GB -> 32768, 6 GB -> none)",
      (hardware.max_context(8), hardware.max_context(12), hardware.max_context(6)) == (8192, 32768, 0))
check("profiles: economy is lighter than balanced",
      performance.settings_for("economy")["llm_context"] < performance.settings_for("balanced")["llm_context"])
check("profiles: full power never picks a context that spills off the GPU",
      performance.settings_for("max")["llm_context"] <= max(hardware.max_context(), 8192))

# -- v0.13: skills, backups, encrypted API key, log file ---------------------------------------------------------
from nexus import backup, skills  # noqa: E402
from nexus.config import DB_PATH, protect, unprotect  # noqa: E402

db.execute("DELETE FROM skills")
check("skills: level curve (1 at 0 XP, 2 at 60, 3 at 180)",
      (skills.level_of(0), skills.level_of(60), skills.level_of(179), skills.level_of(180)) == (1, 2, 2, 3))
check("skills: ranks go from E to S", (skills.rank_of(1), skills.rank_of(10), skills.rank_of(21)) == ("E", "B", "S"))
skills.award("me lembra da reunião amanhã", {"set_reminder"})
check("skills: a reminder credits Organization (topic + tool)",
      db.one("SELECT xp FROM skills WHERE skill = 'organization'")["xp"] == skills.XP_TOPIC + skills.XP_TOOL)
ups = []
for _ in range(6):
    ups += skills.award("crie uma função em python", {"write_file"}, workspace=True)
check("skills: a level-up is reported", any(u["skill"] == "programming" for u in ups), str(ups))
check("skills: summary lists every area", {x["skill"] for x in skills.summary()["skills"]} >= {"organization", "voice"})
memory.new_conversation()
before = sum(r["xp"] for r in db.all("SELECT xp FROM skills"))
memory.set_temporary(True)
script = iter([[("token", "Claro."), ("done", None)]])
_llm.stream_chat = lambda *a, **k: iter(next(script))
assistant.Assistant(lambda e, p: None).ask("como foi a reunião de ontem?")
_llm.stream_chat = real_stream
memory.set_temporary(False)
check("skills: temporary chats earn no XP", sum(r["xp"] for r in db.all("SELECT xp FROM skills")) == before)

zip_path = backup.create()
import zipfile  # noqa: E402

with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
    head = z.read("nexus.db")[:16]
check("backup: zip has a valid database copy and settings", "nexus.db" in names and head == b"SQLite format 3\x00", str(names))
check("backup: a real backup can be scheduled for restore", backup.schedule_restore(str(zip_path))["ok"])
from nexus.config import RESTORE_PENDING  # noqa: E402

RESTORE_PENDING.unlink()
bad = zip_path.parent / "bad.zip"
with zipfile.ZipFile(bad, "w") as z:
    z.writestr("x.txt", "x")
check("backup: an unrelated zip is refused", not backup.schedule_restore(str(bad))["ok"])
check("API key: encrypted at rest and decrypted back", protect("sk-abc").startswith("dpapi:") and unprotect(protect("sk-abc")) == "sk-abc")
check("API key: local placeholder stays as is", protect("ollama") == "ollama")
from nexus import logs  # noqa: E402

logs.setup().info("unit-test-marker")
import sys as _sys  # noqa: E402

_sys.excepthook = _sys.__excepthook__  # the app logs crashes to the file; tests must still show them
check("log file written", "unit-test-marker" in logs.tail(5))

# -- v0.14: links spoken as site names, caches, background, local <-> API switch -------------------------------
check("speech: a link becomes the site's name", voice.clean_for_speech("Veja https://pt.wikipedia.org/wiki/Ada_Lovelace.")
      == "Veja wikipedia.")
check("speech: www links and markdown links", voice.clean_for_speech("Acesse www.python.org/downloads ou [docs](https://x.y/z)")
      == "Acesse python ou docs")
check("speech: .com.br domains", voice.site_name("https://g1.globo.com.br/economia") == "globo")
calls = []


def fake_weather(city="", days=3):
    calls.append(city)
    return {"city": city or "SP", "now": 22}


from nexus import connectors as _cx  # noqa: E402

_cx.clear_cache()
cfg["integrations"] = True
_real_fetch, _real_allowed = _cx.CONNECTORS["weather"].fetch, _cx.online_allowed
_cx.CONNECTORS["weather"].fetch, _cx.online_allowed = fake_weather, lambda: True
tools.get_weather(city="Rio"); tools.get_weather(city="Rio"); tools.get_weather(city="Recife")
check("online cache: same question within the TTL doesn't hit the network", calls == ["Rio", "Recife"], str(calls))
_cx.CONNECTORS["weather"].fetch, _cx.online_allowed = _real_fetch, _real_allowed
knowledge._cache.clear()
first = knowledge.search("estoicismo")
check("knowledge cache: repeated search served from cache", knowledge.search("estoicismo") == first and len(knowledge._cache) >= 1)
knowledge.learn("Teste cache", "conteúdo sobre estoicismo e cache", "aprendido")
check("knowledge cache: cleared when the base changes", len(knowledge._cache) == 0)
lst = voice.Listener.__new__(voice.Listener)
lst.background, lst.model, lst.mode = True, object(), "off"
cfg["require_wake_word"], cfg["bg_wake_only"] = False, True
check("background: only 'Nexus...' counts while minimized/unfocused", lst.wake_required())
lst.background = False
check("foreground: normal conversation again", not lst.wake_required())
lst.released = False
lst.release()
check("minimized: Whisper released from memory when the mic is off", lst.model is None and lst.released)
cfg.update({"ai_target": "local", "ai_local": {}, "ai_api": {}, "llm_preset": "ollama", "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "qwen3:8b", "llm_api_key": "ollama", "network_mode": "offline"})
need = _llm.switch_target("api")
check("AI switch: first time on API asks for setup and leaves offline mode", need and cfg["network_mode"] == "online")
cfg.update({"llm_preset": "openai", "llm_base_url": "https://api.openai.com/v1", "llm_model": "gpt-x", "llm_api_key": "sk-1"})
_llm.switch_target("local")
check("AI switch: back to local restores Ollama", cfg["llm_base_url"].startswith("http://127.0.0.1:11434") and cfg["llm_model"] == "qwen3:8b")
need = _llm.switch_target("api")
check("AI switch: the API configuration (and key) is remembered",
      not need and cfg["llm_model"] == "gpt-x" and cfg["llm_api_key"] == "sk-1")
_llm.switch_target("local")
cfg["network_mode"] = "hybrid"

# -- v0.15: files, library + podcast, browser, automatic network mode ---------------------------------------------
import tempfile as _tf  # noqa: E402
from pathlib import Path as _P  # noqa: E402

from samples import make_docx, make_epub, make_pdf  # noqa: E402

from nexus import browser, files, library, netprobe  # noqa: E402

tmpd = _P(_tf.mkdtemp())
pdf = make_pdf(tmpd / "relatorio.pdf", ["Receita total: 42 mil", "Despesas: 30 mil"])
check("files: PDF text", "Receita total" in files.read(pdf)["text"] and files.read(pdf)["pages"] == 1)
check("files: DOCX text", files.read(make_docx(tmpd / "a.docx", ["Primeiro", "Segundo"]))["text"] == "Primeiro\n\nSegundo")
epub = make_epub(tmpd / "livro.epub", [("Capítulo 1", "Era uma vez um robô. " * 80), ("Capítulo 2", "Ele aprendeu a ler. " * 80)])
check("files: EPUB chapters in order", files.read(epub)["text"].index("Capítulo 1") < files.read(epub)["text"].index("Capítulo 2"))
(tmpd / "x.bin").write_bytes(b"\x00\x01\x02" * 100)
try:
    files.read(tmpd / "x.bin"); unsupported = False
except files.FileError:
    unsupported = True
check("files: binary files are refused with a clear error", unsupported)

book = library.add(epub)
check("library: book added with its text and language", book["chars"] > 1000 and book["title"] == "livro")
pg = library.page(book["id"], 0)
check("library: a page ends at a sentence/paragraph", pg["end"] <= library.PAGE_CHARS and pg["text"].rstrip().endswith((".", "1", "2")))
part, end = library.next_part(book["id"], 0)
check("library: podcast parts are short and end on a sentence", len(part) <= library.PODCAST_CHARS and part.endswith("."))
check("library: find by part of the title", library.find("livr")["id"] == book["id"])

from nexus import app as _app  # noqa: E402


class FakeSpeaker:
    def __init__(self):
        self.said, self.paused = [], __import__("threading").Event()

    def say(self, text, force=False, remember=True, lang_code=None, on_done=None):
        self.said.append(text)
        if on_done and len(self.said) < 3:
            on_done()  # pretend the part was spoken to the end

    def stop(self):
        pass


api = _app.Api.__new__(_app.Api)
api._speaker, api._podcast = FakeSpeaker(), None
api.podcast_start(book["id"], 0)
check("podcast: reads part after part and saves the position",
      len(api._speaker.said) == 3 and library.get(book["id"])["position"] > 0)
api.podcast_stop()
check("podcast: stop clears the player", api.podcast_state() == {"active": False})

opened = []
browser.OPEN = lambda url, new=0: opened.append(url)
cfg["network_mode"] = "hybrid"
check("browser: bare domains get https://", browser.open_url("python.org")["opened"] == "https://python.org")
cfg["network_mode"] = "offline"
check("browser: nothing opens in offline mode", "error" in browser.open_url("https://python.org") and len(opened) == 1)
cfg["network_mode"] = "auto"
for q, exp in (("offline", "offline"), ("slow", "hybrid"), ("fast", "online"), (None, "hybrid")):
    netprobe.state["quality"] = q
    check(f"auto network: {q} connection -> {exp}", netprobe.effective() == exp)
netprobe.state["quality"] = None
cfg["network_mode"] = "hybrid"
big = "Introdução. " * 300 + " O capítulo sobre fotossíntese explica a clorofila. " + "texto irrelevante " * 3000
ctx = assistant.attachment_context("o que diz sobre fotossíntese?", [{"name": "livro.pdf", "text": big}])
check("attachments: big files send the start plus the passages that match the question",
      "fotossíntese" in ctx and len(ctx) <= assistant.ATTACH_CHARS + 400)

# -- v0.15.1: the prompt never overflows the context; background jobs keep the prompt cache ---------------------
memory.new_conversation()
for i in range(15):
    memory.add_message("user", f"Pergunta {i} sobre produtividade?")
    memory.add_message("assistant", "Resposta longa sobre foco e hábitos. " * 60)
cfg["llm_context"] = 8192
hist = assistant._history_messages(300)
check("budget: history stays within its token cap",
      sum(assistant.est_tokens(m["content"]) for m in hist) <= assistant.HISTORY_MAX_TOKENS, str(len(hist)))
check("budget: the newest exchange is kept", hist[-1]["content"].startswith("Resposta longa") and "Pergunta 14" in hist[-2]["content"])
check("budget: history never starts with an answer whose question was dropped", hist[0]["role"] == "user")
check("budget: older long answers are shortened", any(m["content"].endswith("[…]") for m in hist[:-2]) or len(hist) <= 2)
fixed = assistant.est_tokens(assistant.build_system()) + len(json.dumps(assistant.turn_tools())) // 4
check("budget: fixed prompt + history + answer room fit the 8k context",
      fixed + sum(assistant.est_tokens(m["content"]) for m in hist) + 300 + assistant.ANSWER_RESERVE <= 8192)
memory.new_conversation()
assistant._anchors.clear()
cfg["history_turns"] = 6
starts = []
for i in range(14):
    memory.add_message("user", f"msg {i}?")
    memory.add_message("assistant", f"resposta {i}.")
    starts.append(assistant._history_messages(100)[0]["content"])
changes = sum(1 for a, b in zip(starts, starts[1:]) if a != b)
check("window: the start of the history stays put for several turns (prompt cache hits)", changes <= 4, str(starts))
check("window: it never exceeds the configured exchanges", len(assistant._history_messages(100)) <= 12)
memory.set_temporary(True)
for i in range(12):
    memory.add_message("user", f"t{i}?"); memory.add_message("assistant", f"r{i}.")
assistant._history_messages(100)
memory.set_temporary(False); memory.set_temporary(True)  # a new temporary chat: ids start again at 1
memory.add_message("user", "nova conversa temporária?")
check("window: a restarted temporary chat is not left empty", assistant._history_messages(100)[-1]["content"] == "nova conversa temporária?")
memory.set_temporary(False)
cfg["history_turns"] = 12
side = assistant.side_messages("Give this conversation a title.")
nxt = [{"role": "system", "content": assistant.build_system()}, *assistant._history_messages(50)]
check("side jobs reuse the conversation's prompt prefix (prompt cache stays valid)",
      side[0] == nxt[0] and side[1:3] == nxt[1:3])

# -- v0.15.1: AI/API failures get the right explanation and are logged (never with the key) ---------------------
for status, body, kind in ((401, '{"error":{"message":"Incorrect API key provided"}}', "auth"),
                           (429, '{"error":{"type":"insufficient_quota"}}', "billing"), (402, "", "billing"),
                           (429, "Rate limit reached", "rate"), (404, "model 'x' not found", "model"),
                           (503, "overloaded", "server")):
    check(f"API error HTTP {status} -> {kind}", _llm.classify(status, body) == kind)
errors = []
cfg["llm_api_key"] = "sk-secret-123"
_llm.stream_chat = lambda *a, **k: (_ for _ in ()).throw(_llm.LLMOffline("HTTP 401: bad key sk-secret-123", status=401))
assistant.Assistant(lambda e, p: errors.append(p) if e == "error" else None).ask("oi")
_llm.stream_chat = real_stream
check("API error: the user is told the key was refused (not 'start Ollama')",
      errors and errors[0]["kind"] == "auth" and "Ollama" not in errors[0]["message"], str(errors))
check("API error: logged with the reason but without the key",
      "kind=auth" in logs.tail(5) and "sk-secret-123" not in logs.tail(5) and "sk-secret-123" not in errors[0]["detail"])
cfg["llm_api_key"] = "ollama"

# -- v0.15.1: loops cut, answers capped, action log only when relevant --------------------------------------------
loop = "Claro! " + "O barman pergunta de novo: você quer gelo? O programador diz que não. " * 8
check("loop guard: a repeating reply is detected", assistant._looping(loop))
check("loop guard: normal text is not", not assistant._looping("Uma resposta normal. " + " ".join(f"item {i}" for i in range(200))))
check("loop guard: trimmed to the first full repetition", assistant._trim_loop(loop).count("barman") == 1
      and assistant._trim_loop(loop).endswith("não."))
script = iter([[("token", loop[i:i + 20]) for i in range(0, len(loop), 20)] + [("done", None)]])
_llm.stream_chat = lambda *a, **k: iter(next(script))
memory.new_conversation()
assistant.Assistant(lambda e, p: None).ask("me conta uma piada")
_llm.stream_chat = real_stream
check("loop guard: the saved reply has no repetition", memory.history(1)[-1]["content"].count("barman") == 1,
      memory.history(1)[-1]["content"][:200])

db.log_action("dados", "Registrou em 'gastos': 30 livros")
check("action log: not shown for a short unrelated reply ('Letra A')", "recent actions" not in assistant.build_context("Letra A"))
check("action log: shown when the user refers to it", "recent actions" in assistant.build_context("cancela o que você registrou"))

# -- v0.15.1: temporary chat - the model can't memorize on its own ------------------------------------------------
def remember_script():
    return iter([[("tool_calls", [{"id": "r1", "name": "remember", "arguments": '{"content": "tem uma tartaruga Jorge"}'}])],
                 [("token", "Que legal!"), ("done", None)]])


before_mem = len(memory.all_memories())
memory.set_temporary(True)
script = remember_script()
_llm.stream_chat = lambda *a, **k: iter(next(script))
assistant.Assistant(lambda e, p: None).ask("Eu tenho uma tartaruga chamada Jorge.")
blocked = len(memory.all_memories()) == before_mem
script = remember_script()
assistant.Assistant(lambda e, p: None).ask("Lembra que eu tenho uma tartaruga chamada Jorge.")
allowed = len(memory.all_memories()) == before_mem + 1
_llm.stream_chat = real_stream
memory.set_temporary(False)
check("temporary chat: the model can't memorize facts on its own", blocked)
check("temporary chat: an explicit 'lembra que...' still works", allowed)

# -- v0.15.5: beta features, user/developer mode, prompt cache across turns ---------------------------------------
from nexus import features  # noqa: E402

beta_names = {"list_books", "read_book", "open_url", "web_search", "play_music"}
settings["app_mode"] = "user"
user_tools = {x["function"]["name"] for x in assistant.turn_tools()}
check("beta: user mode starts with every beta feature off", not any(features.state()["features"].values()))
check("beta: their tools leave the AI's prompt", not user_tools & beta_names and "add_task" in user_tools)
check("beta: a disabled tool refuses to run", "beta" in str(tools.execute("open_url", {"url": "https://x.org"})))
settings["beta_library"] = True
check("beta: one feature can be enabled alone",
      {"list_books", "read_book"} <= {x["function"]["name"] for x in assistant.turn_tools()} and not features.enabled("browser"))
settings["beta_library"] = False
settings["app_mode"] = "developer"
check("beta: developer mode turns everything on",
      all(features.state()["features"].values()) and beta_names <= {x["function"]["name"] for x in assistant.turn_tools()})
settings["app_mode"] = "user"
check("beta: core features are always on", features.enabled("memory") and features.tool_allowed("add_task"))

seen_prompts = []


def capture_stream(messages, *a, **k):
    seen_prompts.append([dict(m) for m in messages])
    return iter([("token", f"Resposta {len(seen_prompts)}."), ("done", None)])


memory.new_conversation()
_llm.stream_chat = capture_stream
bot = assistant.Assistant(lambda e, p: None)
bot.ask("Quem escreveu Dom Casmurro?")
bot.ask("E Memórias Póstumas?")
_llm.stream_chat = real_stream
first, second = seen_prompts[0], seen_prompts[1]
check("prompt cache: the next turn starts with the same history (system + earlier turns)",
      second[0] == first[0] and second[len(first) - 1]["content"] == "Quem escreveu Dom Casmurro?", str(second[-3:])[:300])
check("prompt cache: the database keeps only the raw text",
      memory.history(5)[0]["content"] == "Quem escreveu Dom Casmurro?")

from datetime import date as _date, timedelta as _td  # noqa: E402

_ctx = assistant.build_context("Me lembra de ligar para o dentista amanhã às 10h.")
check("calendar: 'tomorrow' is labelled with its date (the model picked the 2nd list item)",
      "Tomorrow = " in _ctx and (_date.today() + _td(days=1)).isoformat() in _ctx.split("Tomorrow = ")[1].split(";")[0])

# raw qwen3 prompt: turn N+1 starts with exactly turn N's prompt plus what the model generated
from nexus import llm as _rawllm  # noqa: E402

t_tools = assistant.turn_tools()[:2]
turn1 = [{"role": "system", "content": "S"}, {"role": "user", "content": "oi"}]
call_msg = {"role": "assistant", "content": "", "tool_calls": [
    {"id": "c0", "type": "function", "function": {"name": "add_task", "arguments": '{"title": "pão"}'}}]}
p1 = _rawllm.render_qwen3(turn1, t_tools)
generated = '<tool_call>\n{"name": "add_task", "arguments": {"title":"pão"}}\n</tool_call>'
p2 = _rawllm.render_qwen3(turn1 + [call_msg, {"role": "tool", "content": "{}", "name": "add_task"}], t_tools)
p3 = _rawllm.render_qwen3(turn1 + [{"role": "assistant", "content": "Olá!"}, {"role": "user", "content": "e aí?"}], t_tools)
check("raw prompt: the next turn starts with the previous prompt + the generated answer",
      p3.startswith(p1 + "Olá!<|im_end|>\n") and p3.endswith("<think>\n\n</think>\n\n"))
check("raw prompt: a tool round repeats the generated tool call", p2.startswith(p1 + generated), p2[len(p1):len(p1) + 90])
check("raw prompt: tools listed like Ollama's template", '{"type": "function", "function": {"name":"' in p1)
check("raw prompt: tool calls parsed from the text",
      _rawllm.parse_tool_calls("x" + generated) == [{"id": "call_0", "name": "add_task", "arguments": '{"title": "pão"}'}])
check("raw prompt: tool-call text never reaches the screen",
      _rawllm._visible("Vou anotar.<tool_c") == "Vou anotar." and _rawllm._visible("Ok" + generated, final=True) == "Ok")

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

# -- v0.16: interface texts exist in the three languages; colour settings are valid --------------------------------
import re  # noqa: E402
from pathlib import Path  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "nexus" / "web"
_i18n = (WEB / "i18n.js").read_text("utf-8")
_blocks = dict(zip(("pt", "en", "es"), re.split(r"\n  (?:pt|en|es): \{", _i18n)[1:]))
_keys = {lang: set(re.findall(r"(?:^|[\s,{])([A-Za-z_]\w*): ", body)) for lang, body in _blocks.items()}
for _m in re.finditer(r"Object\.entries\(", _i18n):  # v0.18.0+: keys added as JSON blocks after the main object
    try:
        _extra, _end = json.JSONDecoder().raw_decode(_i18n, _m.end())
    except ValueError:
        continue
    if _i18n.startswith(")) Object.assign(window.I18N[l], extra)", _end):
        for lang, more in _extra.items():
            _keys[lang] |= set(more)
_html = (WEB / "index.html").read_text("utf-8")
_used = set(re.findall(r'data-i18n(?:-ph|-title)?="(\w+)"', _html))
for lang in ("pt", "en", "es"):
    missing = sorted(_used - _keys[lang])
    check(f"i18n: every interface text exists in {lang}", not missing, str(missing[:8]))
_guide = {"guideHint", "gKeys", "gClose", "kGuide", "kPanel", "kMode", "colorsTitle", "colorsReset"}
check("i18n: guide HUD and colour texts in the three languages", all(_guide <= _keys[x] for x in _keys))
_langs = {}
for _l in ("pt", "en", "es"):
    settings["language"] = _l
    _langs[_l] = (assistant.build_system(), assistant.build_context("Oi"), assistant.build_context("Hello there, how are you?"))
settings["language"] = "auto"
check("language switch keeps the system prompt identical (cache stays valid)", _langs["pt"][0] == _langs["en"][0] == _langs["es"][0])
check("reply language travels in the context", "Reply ONLY in English." in _langs["pt"][2]
      and "Reply ONLY in Spanish." in _langs["es"][1])
check("bars/layout/rest settings have defaults",
      settings["ui_layout"] == "computer" and all(settings[k] == "hover" for k in ("bar_top", "bar_left", "bar_right", "bar_bottom"))
      and int(settings["rest_minutes"]) >= 0)
# -- v0.16.5: the AI opens the interface ---------------------------------------------------------------------------
from nexus import ui_nav  # noqa: E402

_nav = {
    "abre as configurações": ("settings", "general"), "Nexus, abre as configurações de voz": ("settings", "voice"),
    "abre os atalhos": ("settings", "keys"), "open settings": ("settings", "general"), "abra o painel": ("panel", None),
    "abre a agenda": ("panel", None), "mostra minhas conversas": ("conversations", None),
    "muéstrame la biblioteca": ("library", None), "mostra o tutorial": ("tutorial", None), "fecha isso": ("close", None),
    "close the menu": ("close", None), "abre as configurações de notificações": ("settings", "notif"),
}
_bad = [k for k, (tg, sec) in _nav.items() if (ui_nav.detect(k) or {}).get("target") != tg
        or (sec and ui_nav.detect(k)["section"] != sec)]
check("ui nav: short 'open X' requests are recognised without the model", not _bad, str(_bad))
_not = ["abre o youtube", "abre o google e pesquisa gatos", "abre o livro dom casmurro",
        "para que serve as configurações?", "fecha a porta da cozinha amanhã cedo por favor"]
check("ui nav: other requests still go to the AI", not [x for x in _not if ui_nav.detect(x)],
      str([x for x in _not if ui_nav.detect(x)]))
_chg = {"Quero mudar a cor do aro do NEXUS, me leva lá": "custom", "change the ring colour": "custom", "quero trocar o cursor": "custom",
        "personalizar os atalhos": "keys", "muda tua voz": "voice", "quero mudar o idioma": "general"}
_bad = [k for k, sec in _chg.items() if (ui_nav.detect(k) or {}).get("section") != sec]
check("ui nav: 'change X of NEXUS' opens the right settings section", not _bad, str(_bad))
check("ui nav: changes that are not about NEXUS stay with the AI",
      not any(ui_nav.detect(x) for x in ("vou mudar de casa amanhã", "mudei o microfone de lugar", "quero alterar minha senha do banco",
                                         "muda a cor do texto do meu documento", "como mudo a cor do aro?")))
check("safety net: 'I opened the settings' without the tool is caught",
      bool(assistant._needs_tool("Aberto o painel de configurações do NEXUS.", False, "quero mudar a cor do aro", set()))
      and not assistant._needs_tool("Aberto o painel de configurações.", True, "quero mudar a cor do aro", {"open_interface"}))
_opened = []
tools.ui_hook = _opened.append
settings["app_mode"] = "user"
_r1 = tools.execute("open_interface", {"target": "settings", "section": "ui"})
_r2 = tools.execute("open_interface", {"target": "library"})
settings["app_mode"] = "developer"
_r3 = tools.execute("open_interface", {"target": "library"})
settings["app_mode"] = "user"
tools.ui_hook = None
check("open_interface: opens a section of the settings", _r1.get("opened") == "settings" and _opened[0]["section"] == "ui")
check("open_interface: beta parts stay closed while their feature is off", "error" in _r2 and _r3.get("opened") == "library")
check("open_interface: the tool is offered to the AI", "open_interface" in {x["function"]["name"] for x in assistant.turn_tools()})
check("ui nav: spoken confirmations exist in the three languages",
      all(all(k in i18n.STRINGS[lng] for k in ("ui_opening", "ui_closing", "ui_beta_off", "ui_n_settings", "ui_n_tutorial"))
          for lng in ("pt", "en", "es")))
check("v0.16.5 settings defaults", settings["show_exchange"] is True and settings["exchange_follow"] is False
      and settings["cursor_style"] == "ring" and settings["shortcuts"] == {})
# -- v0.16.8 -----------------------------------------------------------------------------------------------------
from nexus import app as _app  # noqa: E402

check("optimize: this process's RAM is measured (Windows API)", _app._rss_mb() > 1)
_app._trim_working_set()
check("optimize: giving pages back to Windows doesn't break anything", _app._rss_mb() > 0)
_cm = _app.Api.concept_map()
check("concept map: skills, knowledge areas and memories", len(_cm["skills"]) >= 8 and isinstance(_cm["knowledge"], list)
      and isinstance(_cm["memories"], list))
check("concept map: the AI can open it", (ui_nav.detect("abre o mapa mental") or {}).get("target") == "map"
      and (ui_nav.detect("show me the skill tree") or {}).get("target") == "map")
settings["app_mode"] = "user"
check("beta: concept map and hold-to-talk start off for users",
      not features.enabled("map") and not features.enabled("hold_talk") and settings["speak_menus"] is True)
check("i18n: map name spoken in the three languages", all("ui_n_map" in i18n.STRINGS[x] for x in ("pt", "en", "es")))
# -- v0.17.0: terms & privacy, AMD tuning ------------------------------------------------------------------------
from nexus import gpu_tune, legal  # noqa: E402

check("terms: a new install starts without consent", not legal.accepted())
legal.accept()
_acc = legal.accepted() and settings["terms_accepted_at"]
legal.revoke()
check("terms: accept and revoke", bool(_acc) and not legal.accepted())
_legal_js = (WEB / "legal.js").read_text("utf-8")
check("terms: the interface asks for the same version as nexus/legal.py",
      f'const LEGAL_VERSION = "{legal.VERSION}"' in (WEB / "app.js").read_text("utf-8") and f"Version {legal.VERSION}" in _legal_js)
check("terms: Terms of Use and Privacy Policy in the three languages",
      all(re.search(rf"\b{lng}: {{\s*terms: `", _legal_js) for lng in ("pt", "en", "es")) and _legal_js.count("privacy: `") == 3)
check("privacy policy names every outside service NEXUS talks to",
      all(_legal_js.count(x) >= 3 for x in ("Open-Meteo", "Frankfurter", "Wikip", "Hugging Face", "Google Fonts", "Cloudflare", "DPAPI")))
_lic = (WEB.parent.parent / "LICENSE").read_text("utf-8")
check("license: MIT file present and the terms say so in the three languages (hackathon rule)",
      _lic.startswith("MIT License") and "Bryan Maciel de Almeida" in _lic
      and all(x in _legal_js for x in ("Licença MIT", "MIT License", "Licencia MIT")))
# -- v0.17.5: training mode and memory import (beta) -------------------------------------------------------------
from nexus import memory_import, training  # noqa: E402

check("training: start/finish commands in PT/EN/ES (with topic)",
      training.detect("Nexus, começa o treinamento sobre astronomia") == ("start", "astronomia")
      and training.detect("termina o treinamento") == ("finish", "") and training.detect("start training about chess")[0] == "start"
      and training.detect("termina el entrenamiento") == ("finish", "") and training.detect("vamos estudar JS") is None)
_facts = training.extract_facts(["A Lua leva cerca de 27 dias para orbitar a Terra. Júpiter é o maior planeta.",
                                 "Meu planeta favorito é Saturno.", "Qual é o maior planeta?", "Obrigado!"])
check("training: every statement becomes a fact, personal ones marked, questions skipped",
      [f["personal"] for f in _facts] == [False, False, True] and len(_facts) == 3, str(_facts))
import nexus.training as _tr  # noqa: E402

_real_complete, _real_ev = _tr.llm.complete, _tr.evidence
_tr.llm.complete = lambda *a, **k: '[{"i":1,"verdict":"agree","note":"ok"},{"i":2,"verdict":"disagree","note":"Mercúrio"},{"i":3,"verdict":"unknown","note":""}]'
_tr.evidence = lambda fact: {"local": "", "online": "x", "source": "https://pt.wikipedia.org/wiki/X"}
settings["app_mode"] = "developer"
memory.new_conversation()
_ev = []
_bot = assistant.Assistant(lambda e, p: _ev.append((e, p)))
_bot.ask("começa o treinamento sobre astronomia")
_bot.ask("Júpiter é o maior planeta do Sistema Solar.")
_noted = [p["text"] for e, p in _ev if e == "done"][-1]
_bot.ask("Marte é o planeta mais próximo do Sol. A Lua tem anéis.")
_bot.ask("Meu planeta favorito é Saturno.")
_bot.ask("termina o treinamento")
_tr.llm.complete, _tr.evidence = _real_complete, _real_ev
_res = [p for e, p in _ev if e == "training_done"][0]
_said = [p["text"] for e, p in _ev if e == "done"][-1]
check("training: lessons are noted instantly without the AI", _noted.startswith("Anotado"), _noted)
check("training: analysis keeps confirmed + personal, leaves out contradicted/unchecked",
      [f["verdict"] for f in _res["learned"]] == ["agree", "personal"] and len(_res["left_out"]) == 2, str(_res)[:300])
check("training: agreement counts only what could be compared (1 of 2 = 50%)", _res["score"] == 50 and _said.startswith("Análise completa"))
check("training: confirmed knowledge and personal memory are saved; session is in the history",
      any(d["category"] == "Aprendizados" for d in knowledge.documents())
      and any(m["source"] == "training" for m in memory.all_memories()) and training.history()[0]["score"] == 50)
settings["app_mode"] = "user"
_ans = "Claro:\n- [preferencia] Gosta de chá verde.\n- [trabalho] Trabalha com dados.\n* [xyz] Mora no Rio.\nEspero ter ajudado!"
check("memory import: one memory per list line, unknown categories become 'outros'",
      memory_import.parse(_ans) == [("preferencia", "Gosta de chá verde."), ("trabalho", "Trabalha com dados."), ("outros", "Mora no Rio.")])
_imp1 = memory_import.import_text("chatgpt", _ans)
_imp2 = memory_import.import_text("claude", "- [preferencia] Gosta de chá verde.")
check("memory import: tagged by source, duplicates skipped", _imp1["added"] == 3 and _imp2["added"] == 0 and _imp2["skipped"] == 1
      and any(x["source"] == "chatgpt" and x["count"] == 3 for x in memory_import.by_source()))
check("memory import: ready-made prompt in the three languages; 'NONE' imports nothing",
      all(len(memory_import.prompt(x)) > 200 for x in ("pt", "en", "es")) and memory_import.import_text("gemini", "NENHUMA")["added"] == 0)
check("beta: training and memory import start off for users", not features.enabled("training") and not features.enabled("memory_import"))
_gs = gpu_tune.status()
check("gpu tuning: status reports card, backend and setting", set(_gs) >= {"amd", "vulkan", "applied", "suggest", "installed"})
check("colours: default ring/core/background are valid hex colours",
      all(re.fullmatch(r"#[0-9a-f]{6}", str(settings[k])) for k in ("color_ring", "color_core", "color_bg")))

# -- v0.18.0: integrations hub, media, apps ------------------------------------------------------------------------
from nexus import apps as _apps  # noqa: E402
from nexus import connectors as cx  # noqa: E402
from nexus import legal as _legal  # noqa: E402
from nexus import media as _media  # noqa: E402

settings["home_city"], settings["language"] = "São Paulo", "pt"
_routes = {q: [c for c, _ in cx.route(q)] for q in (
    "Quanto está o dólar hoje?", "quanto é 100 dólares em reais", "gastei 42 reais no mercado", "quantos reais eu tenho?",
    "Vai chover amanhã em São Paulo?", "o tempo em geral é curto", "quanto tempo falta pro natal?", "quanto está o bitcoin?",
    "que horas são em Tóquio?", "que horas são?", "traduza bom dia para inglês", "qual o próximo feriado?",
    "quanto é 15% de 230?", "10 milhas em km", "notícias sobre tecnologia", "me conta uma piada")}
check("hub: each question reaches only the integration it needs (none for chat, expenses or 'what time is it?')", _routes == {
    "Quanto está o dólar hoje?": ["currency"], "quanto é 100 dólares em reais": ["currency"], "gastei 42 reais no mercado": [],
    "quantos reais eu tenho?": [], "Vai chover amanhã em São Paulo?": ["weather"], "o tempo em geral é curto": [],
    "quanto tempo falta pro natal?": [], "quanto está o bitcoin?": ["crypto"], "que horas são em Tóquio?": ["clock"],
    "que horas são?": [], "traduza bom dia para inglês": ["translate"], "qual o próximo feriado?": ["holidays"],
    "quanto é 15% de 230?": ["calc"], "10 milhas em km": ["units"], "notícias sobre tecnologia": ["news"],
    "me conta uma piada": []}, str(_routes))
check("hub: arguments come from the message (amount, currencies, city, days, language)",
      cx.route("quanto é 100 dólares em reais")[0][1] == {"amount": 100.0, "from_currency": "USD", "to_currency": "BRL"}
      and cx.route("Vai chover amanhã em Curitiba?")[0][1] == {"city": "Curitiba", "days": 2}
      and cx.route("how much is 50 euros in dollars?")[0][1]["to_currency"] == "USD"
      and cx.route("como se diz obrigado em japonês?")[0][1]["target"] == "ja")
check("calculator: exact answers without the AI (percent, words, roots, division)",
      [cx.prepare(q)["instant"] for q in ("quanto é 15% de 230?", "quanto é 12 x 7 + 3", "raiz quadrada de 144",
                                          "quanto é 10 dividido por 4")]
      == ["15% de 230 = 34,5.", "12 x 7 + 3 = 87.", "raiz quadrada de 144 = 12.", "10 dividido por 4 = 2,5."])
check("units: length, temperature and mass", [cx.prepare(q)["instant"] for q in ("10 milhas em km", "30 graus celsius em fahrenheit",
                                                                                   "converte 5 kg em libras")]
      == ["10 milhas = 16,09 quilômetros.", "30 graus Celsius = 86 graus Fahrenheit.", "5 quilos = 11,02 libras."])
check("calculator: code never runs (only arithmetic is evaluated)", cx.route("quanto é __import__('os')") == []
      and cx.route("quanto é 2**10000000") == [])
_cx_calls = []


def _fake_currency(amount=1, from_currency="USD", to_currency="BRL"):
    _cx_calls.append((amount, from_currency, to_currency))
    return {"amount": amount, "from": from_currency, "to": to_currency, "result": round(5.0828 * amount, 4),
            "rate_date": "2026-10-16", "source": "test"}


_real = cx.CONNECTORS["currency"].fetch, cx.online_allowed
cx.CONNECTORS["currency"].fetch, cx.online_allowed = _fake_currency, lambda: True
cx.clear_cache()
_a = cx.prepare("Quanto está o dólar hoje?")
_b = cx.prepare("Quanto está o dólar hoje?")
check("currency: instant answer with names and symbol", _a["instant"] == "1 dólar = R$ 5,08 (cotação de referência do BCE de 16/10).",
      str(_a["instant"]))
check("hub cache: the second question doesn't use the internet", len(_cx_calls) == 1 and _b["instant"] == _a["instant"])
_long = cx.prepare("Quanto está o dólar hoje? Estou pensando em viajar para os Estados Unidos no fim do ano e queria planejar")
check("hub: a longer question gets the data in the context for the model (no tool round)",
      _long["instant"] is None and "Live data" in _long["block"] and "5.0828" in _long["block"])
cx.online_allowed = lambda: False
cx._load()["data"] = {k: [v[0] - 99999, v[1]] for k, v in cx._load()["data"].items()}  # expired copy
_off = cx.call("currency", {"amount": 1.0, "from_currency": "USD", "to_currency": "BRL"})
check("offline: the last copy is used and marked as possibly outdated", _off.get("stale_from") and len(_cx_calls) == 1)
cx.CONNECTORS["currency"].fetch, cx.online_allowed = _real
cx.toggle("currency", False)
check("integration turned off: no answer, no tool", cx.route("Quanto está o dólar hoje?") == []
      and "convert_currency" not in {x["function"]["name"] for x in assistant.turn_tools()})
cx.toggle("currency", True)
check("lookup tool lists only the integrations that are on", "lookup" in {x["function"]["name"] for x in assistant.turn_tools()}
      and next(x for x in assistant.turn_tools() if x["function"]["name"] == "lookup")["function"]["parameters"]
      ["properties"]["service"]["enum"] == ["crypto", "clock", "translate", "holidays", "air"])
_c1 = cx.add_custom("Gasolina", "gasolina, combustível", "https://api.exemplo.com/gas?q={query}", 60)
_c2 = cx.add_custom("Ruim", "x", "http://inseguro.com/x")
check("custom integrations: https only, routed by keyword, removable",
      _c1["ok"] and not _c2["ok"] and cx.route("quanto está a gasolina em Curitiba?")[0][0] == _c1["id"]
      and cx.remove_custom(_c1["id"])["ok"] and not settings["custom_connectors"])
check("hub status: every integration with its state", {x["id"] for x in cx.status()} >= set(cx.ORDER)
      and all(x["state"] in ("off", "active", "offline", "error", "cached", "sleeping") for x in cx.status()))
check("media: phrases recognised without the AI (and not ordinary talk)", [(_media.detect(q) or {}).get("action") for q in (
    "pausa a música", "próxima música", "volume em 30%", "aumenta o volume", "o que está tocando?", "música para estudar",
    "para de falar", "aumenta", "what song is this", "baja el volumen")]
      == ["pause", "next", "volume", "volume_up", "now_playing", None, None, None, "now_playing", "volume_down"])
_apps._apps, _apps._loaded = [{"name": "Visual Studio Code", "id": "Microsoft.VisualStudioCode"},
                              {"name": "RetroArch", "id": "D:\\Emuladores\\RetroArch\\retroarch.exe"},
                              {"name": "Steam", "id": "{7C5A40EF}\\Steam\\Steam.exe"},
                              {"name": "Wallpaper Engine", "id": "steam://rungameid/431960"},
                              {"name": "Counter-Strike 2", "id": "steam://rungameid/730"},
                              {"name": "WhatsApp", "id": "5319275A.WhatsAppDesktop!App"}], 1e12
check("apps: found by name or nickname", [(_apps.detect(q) or {}).get("name") for q in (
    "abre o vscode", "abre o zap", "vamos jogar counter-strike 2", "abre o Discord", "abre o arquivo relatório.pdf")]
      == ["Visual Studio Code", "WhatsApp", "Counter-Strike 2", None, None])
check("apps: games, launchers and work apps (the user can change it)",
      [_apps.kind(a) for a in _apps._apps] == ["work", "game", "launcher", "work", "game", "work"])
settings["apps_work"] = ["RetroArch"]
check("apps: marked by the user", _apps.kind(_apps._apps[1]) == "work")
settings["apps_work"] = []
_opened = []
_real_launch, _real_hook = _apps.launch, tools.app_hook
_apps.launch = lambda app: _opened.append(app["name"]) or {"ok": True, "name": app["name"], "kind": _apps.kind(app)}
tools.app_hook = lambda app: _opened.append("suspend:" + app["name"])
settings["app_mode"] = "developer"
_ev = []
_bot = assistant.Assistant(lambda e, p: _ev.append((e, p)))
_bot.ask("vamos jogar counter-strike 2")
_said = [p["text"] for e, p in _ev if e == "done"][-1]
check("apps: a game opens and NEXUS suspends itself to free the graphics card",
      _opened == ["Counter-Strike 2", "suspend:Counter-Strike 2"] and "suspenso" in _said, f"{_opened} {_said}")
_ev.clear()
_bot.ask("quanto é 15% de 230?")
check("assistant: the calculator answers without the model and the exchange is in the history",
      [p["text"] for e, p in _ev if e == "done"] == ["15% de 230 = 34,5."] and memory.history(1)[-1]["content"] == "15% de 230 = 34,5.")
_apps.launch, tools.app_hook = _real_launch, _real_hook
settings["app_mode"] = "user"
check("beta: media and apps start off for users", not features.enabled("media") and not features.enabled("apps")
      and "open_app" not in {x["function"]["name"] for x in assistant.turn_tools()})
check("terms 1.2: new services are listed (and accepted again)", _legal.VERSION == "1.2" and all(
    w in (_isolated.ROOT / "nexus" / "web" / "legal.js").read_text("utf-8") for w in ("CoinGecko", "MyMemory", "Nager.Date")))

# -- v0.18.1: the microphone hearing NEXUS itself or noise ----------------------------------------------------------
check("speech: emojis are not read aloud", voice.clean_for_speech("Vamos brincar. 😄 Posso contar uma piada 👍🏽 ✓")
      == "Vamos brincar. Posso contar uma piada")
_said = ("Claro, Bryan! Vamos brincar. Que tipo de brincadeira você quer? Posso contar uma piada, jogar um jogo de "
         "perguntas e respostas, ou algo mais? cara sorrindo de boca aberta")
check("echo: NEXUS's own words coming back right after it spoke are ignored",
      voice.is_echo("Cara sorrindo de boca aberta e olha o sonho", _said)
      and voice.is_echo("Jogar um jogo de perguntas e respostas, ou algo mais.", _said))
check("echo: replies that reuse its words still count",
      not voice.is_echo("Conta uma piada", _said) and not voice.is_echo("Me fala sobre filosofia estoica", _said)
      and not voice.is_echo("sim, jogar um jogo de perguntas", _said, right_after=False))
check("noise: Whisper's invented phrases and loops are dropped",
      voice.is_hallucination("Você tem um clima? Você tem um clima? Você tem um clima?")
      and voice.is_hallucination("Legendas pela comunidade de Amara.org") and not voice.is_hallucination("Qual a previsão do tempo?")
      and not voice.is_hallucination("Sim. Sim. Pode marcar às dez."))


class _Seg:
    def __init__(self, text, nsp=0.1, lp=-0.3, cr=1.2):
        self.text, self.no_speech_prob, self.avg_logprob, self.compression_ratio = text, nsp, lp, cr


class _Model:
    def __init__(self, segs):
        self.segs = segs

    def transcribe(self, *a, **k):
        return iter(self.segs), None


class _Spk:
    def recent_speech(self):
        return _said
    ended_at = 0.0


_heard = []
_lst = voice.Listener.__new__(voice.Listener)
_lst.model_state, _lst.mode, _lst.background, _lst.awake_until = "ready", "live", False, 0
_lst.on_text, _lst.on_state, _lst.speaker, _lst.dropped = (lambda t, d: _heard.append(t)), (lambda s: None), _Spk(), []
_lst.model = object()
cfg["require_wake_word"], cfg["bg_wake_only"] = False, True
_lst.seg_start = _lst.speaker.ended_at + 1.0
for _segs in ([_Seg(" Que tipo de brincadeira você quer?")], [_Seg(" Você tem um clima?"), _Seg(" Você tem um clima?"),
                                                              _Seg(" Você tem um clima?")],
              [_Seg(" Obrigado.", nsp=0.9, lp=-0.9)], [_Seg(" Conta uma piada.")]):
    _lst.model = _Model(_segs)
    _lst._handle(np.zeros(16000, dtype=np.float32), False)
check("listening: echo, loops and noise never reach the AI; the real reply does",
      _heard == ["Conta uma piada."] and [r for r, _ in _lst.dropped] == ["echo", "noise"], f"{_heard} {_lst.dropped}")

# -- v0.18.5: NEXUS changes its own settings, exact tabs, AMD panel ------------------------------------------------
from nexus import amd as _amd  # noqa: E402
from nexus import prefs as _prefs  # noqa: E402
from nexus import ui_nav as _nav  # noqa: E402

_d = {q: (_prefs.detect(q) or {}).get("changes") for q in (
    "muda o aro para vermelho", "aro vermelho e núcleo branco", "make the ring red", "pon el fondo negro", "tema AMD",
    "voz feminina", "aro maior", "quero mudar a cor do aro", "qual a cor do aro?", "o aro vermelho estava lindo ontem quando eu abri")}
check("prefs: requests recognised without the AI (and not questions or chat)", _d == {
    "muda o aro para vermelho": {"color_ring": "#ff3030"}, "aro vermelho e núcleo branco": {"color_ring": "#ff3030", "color_core": "#f5f7fa"},
    "make the ring red": {"color_ring": "#ff3030"}, "pon el fondo negro": {"color_bg": "#05060a"}, "tema AMD": {"theme": "amd"},
    "voz feminina": {"voice_gender": "female"}, "aro maior": {"ring_scale": 115}, "quero mudar a cor do aro": None,
    "qual a cor do aro?": None, "o aro vermelho estava lindo ontem quando eu abri": None}, str(_d))
_ring0 = settings["color_ring"]
_applied = _prefs.apply({"theme": "amd"})
check("prefs: a theme sets the three colours; undo brings them back",
      _applied["color_core"] == "#ed1c24" and settings["theme"] == "amd" and _prefs.undo() and settings["color_ring"] == _ring0)
check("prefs: values are validated (ranges, colour names, unknown settings refused)",
      _prefs.validate("ring_scale", 500) == 140 and _prefs.validate("color_ring", "azul") == "#2f86ff"
      and "error" in _prefs.set_preference("llm_api_key", "x") and "error" in _prefs.set_preference("color_core", "banana"))
_seen = []
tools.prefs_hook = _seen.append
_ev = []
_bot = assistant.Assistant(lambda e, p: _ev.append((e, p)))
_bot.ask("muda o fundo para preto")
check("prefs: instant change, the interface is told, and the reply confirms it",
      settings["color_bg"] == "#05060a" and _seen == [{"color_bg": "#05060a"}]
      and [p["text"] for e, p in _ev if e == "done"][-1] == "Pronto: fundo na nova cor.")
_bot.ask("desfaz")
check("prefs: 'desfaz' undoes the last change", settings["color_bg"] != "#05060a")
tools.prefs_hook = None
check("prefs: the model is made to call set_preference when it only claims the change",
      assistant._needs_tool("Pronto: tema AMD.", False, "tema AMD", set()) is not None
      and assistant._needs_tool("Pronto.", False, "tema AMD", {"set_preference"}) is None
      and assistant._needs_tool("O aro é azul.", False, "qual a cor do aro?", set()) is None)
check("navigation: exact settings sections and panel tabs",
      [_nav.detect(q) for q in ("abre a aba AMD", "abre a personalização", "quero mudar a cor do aro", "abre minhas memórias",
                                "abre os aprendizados", "abre as configurações de ativação")]
      == [{"target": "settings", "section": "amd"}, {"target": "settings", "section": "custom"},
          {"target": "settings", "section": "custom"}, {"target": "panel", "section": "memory"},
          {"target": "panel", "section": "learned"}, {"target": "settings", "section": "listen"}])
_opened = []
tools.ui_hook = _opened.append
tools.open_interface("panel", "learned"); tools.open_interface("panel", "nonsense")
check("open_interface: panel tabs pass, unknown tabs are dropped", [o["section"] for o in _opened] == ["learned", None])
tools.ui_hook = None
_info = _amd.info()
check("AMD panel: card info read from the driver's registry keys (no extra software)",
      isinstance(_info.get("cards"), list) and all({"name", "vram_gb", "driver", "adrenalin"} <= set(c) for c in _info["cards"]))
_live = _amd.live()
check("AMD panel: live load and memory from Windows counters",
      "error" in _live or {"gpu_pct", "vram_used_mb", "ai_vram_mb", "ai_gpu_pct"} <= set(_live))
check("AMD panel: references only open known AMD addresses", not _amd.open_reference("https://evil.example")
      and all(u.startswith("https://") for _, u in _amd.REFERENCES))
_llm.STATS.clear()
_llm._record({"eval_count": 80, "eval_duration": 4e9, "prompt_eval_count": 3000, "prompt_eval_duration": 3e8}, 0.0, 1.5)
_ps = _llm.perf_summary()
check("AI speed: tokens/s and time to the first word kept for the AMD panel", _ps["tok_s"] == 20.0 and _ps["first_s"] == 1.5
      and _ps["history"] == [20.0])
settings["app_mode"] = "user"
check("prompt: tool list kept short (descriptions trimmed for the new set_preference)",
      len(json.dumps(assistant.turn_tools(), ensure_ascii=False)) < 10500
      and "set_preference" in {x["function"]["name"] for x in assistant.turn_tools()})

# -- v0.18.6: local models for better and weaker PCs -----------------------------------------------------------------
from nexus import models as _models  # noqa: E402

check("models: the recommended model follows the PC (no card/4 GB -> Lite, 6 GB -> Mini, 8 GB -> NEX-1.0, 12-16 GB -> Pro, 24 GB -> Max)",
      [_models.recommended(v, r) for v, r in ((0, 8), (0, 16), (4, 16), (6, 16), (8, 16), (12, 32), (16, 32), (24, 64))]
      == ["qwen3:1.7b", "qwen3:4b-instruct-2507-q4_K_M", "qwen3:1.7b", "qwen3:4b-instruct-2507-q4_K_M", "qwen3:8b", "qwen3:14b",
          "qwen3:14b", "qwen3:30b-a3b"])
check("models: the Ollama 'qwen3:4b' tag (a thinking model, 69.6 s per answer) is not in the catalog",
      "qwen3:4b" not in _models.BY_ID and _models.MEASURED["qwen3:4b-instruct-2507-q4_K_M"]["avg_answer_s"] < 10)
_f = {m["id"]: _models.fit(m, 8, 16)["status"] for m in _models.CATALOG}
check("models: on an 8 GB card + 16 GB RAM the Pro spills to RAM and the Max doesn't fit",
      _f == {"qwen3:1.7b": "gpu", "qwen3:4b-instruct-2507-q4_K_M": "gpu", "qwen3:8b": "gpu", "qwen3:14b": "partial", "qwen3:30b-a3b": "no"}, str(_f))
check("models: without a usable card the small ones run on the processor",
      _models.fit(_models.BY_ID["qwen3:1.7b"], 0, 16)["status"] == "cpu")
check("models: product names (NEX-1.0 Lite / Pro) and unknown models keep their own name",
      _models.display_name("qwen3:14b") == "NEX-1.0 Pro" and _models.display_name("qwen3:8b") == "NEX-1.0"
      and _models.display_name("llama3:70b") == "NEX · llama3:70b")
_real_inst = _models.installed
_models.installed = lambda: {"qwen3:8b", "qwen3:4b-instruct-2507-q4_K_M"}
_cat = _models.catalog()
check("models: catalog marks installed, active and recommended", [m["installed"] for m in _cat["models"]] == [False, True, True, False, False]
      and sum(m["active"] for m in _cat["models"]) <= 1)
check("models: switching to a model that isn't installed is refused", not _models.use("qwen3:14b")["ok"])
_models.installed = _real_inst

# -- v0.19.0: accounts, downloads, storage, AMD technologies, conversation fixes ----------------------------------
import time as _time  # noqa: E402

from nexus import accounts as _acc  # noqa: E402
from nexus import app as _app  # noqa: E402
from nexus import downloads as _dl  # noqa: E402
from nexus import storage as _st  # noqa: E402

check("colours: shades the user asked for (rosa choque, preto absoluto, vinho, X escuro/claro)",
      [(_prefs.detect(q) or {}).get("changes") for q in ("mude o fundo para rosa choque", "mude o fundo para preto absoluto",
                                                         "fundo vinho", "aro azul escuro", "aro laranja escuro")]
      == [{"color_bg": "#ff1493"}, {"color_bg": "#000000"}, {"color_bg": "#7b1028"}, {"color_ring": "#0b1f5c"},
          {"color_ring": _prefs._shade("#f97316", "dark")}])
_prefs.apply({"color_bg": "#ff00ff"})
check("colours: 'isso é magenta, não rosa choque' re-applies the colour meant",
      (_prefs.detect("isso é magenta, não rosa choque") or {}).get("changes") == {"color_bg": "#ff1493"})
check("safety net: 'Pronto: fundo atualizado para magenta.' without the tool makes the model call it",
      bool(assistant._needs_tool("Pronto: fundo atualizado para magenta.", False, "isso é magenta, não rosa choque", set())))
tools.current_text = "Romântica"
_svc1 = tools._service_asked("spotify")
tools.current_text = "abra pelo yt music"
check("music: Spotify / YouTube Music only when the user named them", _svc1 == settings.get("music_player", "youtube")
      and tools._service_asked("youtube music") == "youtube music")
tools.current_text = ""
_acc_root0 = _acc.ROOT
check("accounts: one account and no password -> no login screen", not _acc.needs_login() and len(_acc.list_accounts()) == 1)
_new = _acc.create("Ana Teste", "abcd")
check("accounts: a second account with its own folder; the password is stored only as a hash",
      _new["ok"] and _acc.folder(_new["account"]["id"]).is_dir() and "abcd" not in _acc.FILE.read_text("utf-8")
      and len(_acc.get(_new["account"]["id"])["hash"]) == 64)
_aid = _new["account"]["id"]
check("accounts: right / wrong password", _acc.check(_aid, "abcd") and not _acc.check(_aid, "x"))
for _ in range(5):
    _acc.check(_aid, "nope")
check("accounts: 5 wrong tries in a minute -> waits (even the right password)", _acc.throttled(_aid) and not _acc.check(_aid, "abcd"))
_acc._fails.clear()
_acc._skip_login = None
check("accounts: with two accounts NEXUS asks who is using it", _acc.needs_login())
_env = _acc.relaunch_env(_aid, unlocked=True)
check("accounts: switching restarts in the account's folder with a one-time token (not a reusable flag)",
      _env["NEXUS_HOME"] == str(_acc.folder(_aid)) and _env["NEXUS_ACCOUNT"] == _aid and len(_env["NEXUS_HANDOFF"]) == 32
      and _acc.HANDOFF.exists())
_acc.HANDOFF.unlink(missing_ok=True)
_genv = _acc.relaunch_env("guest", unlocked=False)
check("guest: a temporary folder, outside the accounts", "nexus-guest-" in _genv["NEXUS_HOME"] and "NEXUS_HANDOFF" not in _genv)
import shutil as _sh  # noqa: E402

_sh.rmtree(_genv["NEXUS_HOME"], ignore_errors=True)
_locked_api = _app.Api.__new__(_app.Api)
object.__setattr__(_locked_api, "_locked", True)
check("locked: data calls answer nothing, the login calls work",
      _locked_api.dashboard() == {"locked": True} and _locked_api.history() == {"locked": True}
      and _locked_api.account_state.__name__ == "account_state")
check("accounts: deleting needs the password and never the owner", not _acc.delete("owner", "")["ok"]
      and not _acc.delete(_aid, "wrong")["ok"] and _acc.delete(_aid, "abcd")["ok"] and not _acc.folder(_aid).exists())
_acc._skip_login = None
_d = _dl.start("model", "teste", 1000)
_dl.update(_d, 400)
_s1 = next(i for i in _dl.state()["items"] if i["id"] == _d)
_dl.ITEMS[_d]["progress_at"] -= 30
_s2 = next(i for i in _dl.state()["items"] if i["id"] == _d)
_dl.finish(_d, True)
check("downloads: progress, 'stalled' after 20 s without bytes, and the log", _s1["pct"] == 40.0 and not _s1["stalled"]
      and _s2["stalled"] and any("done" in line["text"] for line in _dl.state()["log"]))
_rep = _st.report(with_models=False)
check("storage: database, folders, program and free disk", {"db_bytes", "data_bytes", "tables", "parts", "program_bytes",
                                                            "disk_free"} <= set(_rep) and any(t["key"] == "memories" for t in _rep["tables"]))
check("AMD technologies: each one active / available / not on this PC, with ROCm explained",
      {t["id"] for t in _amd.technologies()} == {"radeon_vulkan", "rocm", "adrenalin", "ryzen_cpu", "ryzen_ai", "amd_counters"}
      and all(t["status"] in ("active", "available", "unsupported") for t in _amd.technologies()))
check("voice: the bundled model is found when the build ships it", voice.bundled_model("nonexistent-size") is None)
memory.new_conversation()
tools.ui_hook = lambda nav: None
_bot2 = assistant.Assistant(lambda e, p: None)
_bot2.ask("abre minhas memórias")
check("navigation replies are kept in the history (the next question knows what opened)",
      [m["role"] for m in memory.history(2)] == ["user", "assistant"])
tools.ui_hook = None

# -- v0.19.5: ROCm and NPU -------------------------------------------------------------------------------------------
from nexus import gpu_tune as _gt  # noqa: E402

check("ROCm: each Radeon's chip", [_amd.gfx(n) for n in ("AMD Radeon RX 6600 XT", "AMD Radeon RX 7900 XTX", "AMD Radeon RX 6800",
                                                         "AMD Radeon RX 9070 XT", "AMD Radeon 780M", "NVIDIA RTX 4070")]
      == ["gfx1032", "gfx1100", "gfx1030", "gfx1201", "gfx1103", ""])
_real_targets = _amd.rocm_targets
_amd.rocm_targets = lambda: {"gfx1030", "gfx1100", "gfx1101", "gfx1102", "gfx1150", "gfx1151", "gfx1200", "gfx1201", "gfx906"}
check("ROCm: offered only for chips Ollama ships ROCm libraries for (an RX 6600 XT falls back to the CPU)",
      not _amd.rocm_support("AMD Radeon RX 6600 XT")["supported"] and _amd.rocm_support("AMD Radeon RX 7800 XT")["supported"])
_real_info = _amd.info
_amd.info = lambda: {"cards": [{"name": "AMD Radeon RX 6600 XT", "vram_gb": 8, "driver": "", "adrenalin": ""}]}
check("ROCm: choosing it on an unsupported card is refused (nothing changes)",
      _gt.set_backend("rocm") == {"ok": False, "error": "unsupported"} and _gt.compare_backends("qwen3:8b")["ok"] is False)
_amd.info, _amd.rocm_targets = _real_info, _real_targets
check("NPU: AMD Lemonade preset (OpenAI-compatible, local) and its reference",
      any(pr["id"] == "lemonade" and pr["local"] for pr in _llm.PRESETS) and "lemonade" in dict(_amd.REFERENCES))
check("NPU: detection never fails (a list) and Lemonade reports running or not",
      isinstance(_amd.npus(), list) and set(_amd.lemonade()) >= {"running", "url", "models"})

print(f"\n{len(failures)} failure(s)")
raise SystemExit(1 if failures else 0)
