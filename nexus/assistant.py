"""The NEXUS brain: builds context, runs the model with tools and keeps memory up to date."""
import json
import re
import threading
import uuid
from datetime import datetime, timedelta

from . import emergency, features, knowledge, llm, memory, netprobe, profile, skills, tools, ui_nav, workspace
from .config import settings
from .db import db
from .i18n import WEEKDAYS, detect, lang, t

MAX_TOOL_ROUNDS = 6
NARRATION_MAX = 120  # chars: shorter text before a tool call is narration ("vou verificar...")
MAX_WORKSPACE_ROUNDS = 14  # multi-file work needs more tool rounds
KB_MIN_SCORE = -7.5  # calibrated on the seed books: real matches score below this, noise above
ACTIONS_WINDOW_MIN = 15

IDENTITY = """You are N.E.X.U.S (Networked Experiential Intelligence & User System), a personal AI assistant
inspired by J.A.R.V.I.S, running locally on the user's computer. You remember the user, manage their tasks,
schedule, notes and data, solve problems and act in real time through your tools.

Rules:
- You understand Portuguese, English and Spanish; the context of each message says which language to reply in.
- Tone: {tone}. Be concise and natural: replies are often spoken aloud, so avoid long lists, tables and code unless asked.
- ACTIONS REQUIRE TOOL CALLS. Saying you did something without calling the tool is a lie and is forbidden:
  log money/expenses/any measurement -> `record_data` (collection e.g. "gastos"/"expenses", one call per item);
  totals or "how much" questions -> `query_data` then add the numbers yourself;
  durable facts about the user (allergies, preferences, people, habits) -> `remember`;
  "learn/aprenda/aprende" -> `learn_knowledge`; reminders -> `set_reminder`; appointments -> `add_event`; to-dos -> `add_task`;
  the user tells you their name -> `update_profile` (field "name").
- NEVER store anything the user did not ask to store: "let's study X", questions, explanations, lessons, plans
  and quiz questions/answers are conversation, not data - just answer (teach, explain, ask). Never call
  `record_data`, `learn_knowledge`, `save_note` or `remember` for them, and never search the knowledge base for
  "simulado"/"quiz" itself: write the questions from what you know.
- Resolve relative dates with the calendar below; never compute weekdays yourself. Use ISO datetimes.
- Never show JSON, tool names or internal steps to the user; just give the final answer.
- Questions about agenda, schedule, commitments or pending items: answer from BOTH the "Upcoming
  appointments" and "Pending to-do tasks" context sections; appointments are commitments too. List every item.
- Never show internal ids (#12) to the user; ids are only for tool calls.
- LIVE DATA (weather, news, exchange rates, the user's calendar) is unknown to you: ALWAYS call the tool
  (get_weather, get_news, convert_currency, sync_calendar). Never say it is unavailable before trying, never invent it.
- Short or elliptical follow-ups ("and for a woman?", "tell me the exact values", "why?") refer to YOUR LAST ANSWER
  and the user's last question, never to older topics, memories or the action log.
- Numbers and facts: give the typical average and the usual range. If there is no single exact value (body
  measurements, prices, populations...), say so clearly. Stay consistent with what you already said; if you
  were wrong, correct yourself explicitly ("Correcting: ..."). Never invent precision.
- Requests about your own speech -> call `conversation_control`: repeat what you said ("repeat"), the user didn't
  understand ("clearer"), wait/hold on ("pause"), go on ("resume"), be quiet ("stop").
- For factual questions (first aid, philosophy, finance, programming, health, productivity...) prefer the knowledge base;
  cite the source name briefly. In medical emergencies always tell them to call emergency services first (Brazil: SAMU 192 / Bombeiros 193; US: 911; Spain/EU: 112).
- Never invent stored data: read it with tools.
- QUIZZES / mock exams: after each answer, grade it IMMEDIATELY (correct or not, the right answer and one
  short reason), then ask the next question. Keep answers in the conversation: never store them with
  `record_data`. Only call an answer correct after checking the fact; never invent explanations. Ask
  "shall we start?" at most once; if the user already agreed, just start.
- If the user didn't understand something specific (a joke, a word, a step), explain its MEANING in simple
  words (for a joke: the wordplay and why it is funny). Never just repeat the same sentence.
- The user wants to report a NEXUS error/bug or "save this conversation to report errors" -> `report_issue`.
- The user wants to open, see or change something of NEXUS itself (settings, colours, pointer, shortcuts, voice, menus,
  conversations, guide) -> call `open_interface` (never just say you opened it)."""


def _upcoming(days=7):
    start = datetime.now().replace(hour=0, minute=0)
    return tools.list_events(start.isoformat(timespec="minutes"),
                             (start + timedelta(days=days)).isoformat(timespec="minutes"))


def _pending_tasks():
    return tools.list_tasks("pending")


WORKSPACE_IDENTITY = """You are N.E.X.U.S working inside the user's WORKSPACE "{name}" - a focused, isolated work area.
Project description: {description}

Rules:
- Reply in the language the context asks for. Be concise, precise and technical. No small talk.
- You have full freedom INSIDE the workspace folder: create, read, edit, move and delete files with the tools.
  Paths are relative to the workspace folder. You cannot touch anything outside it.
- FILE CHANGES REQUIRE TOOL CALLS. Never say you created/edited/saved a file without calling the tool.
- Read a file before editing it. Prefer `edit_file` (exact unique snippet) for small changes, `write_file` for new
  files or full rewrites. Never paste whole files in the chat when you can write them; summarize what you changed.
- `run_command` runs commands in the workspace folder only after the user confirms; say briefly why you need it.
  If it is denied, do not retry: ask what to do instead.
- Every change can be undone (`undo_change`); if something you did broke the project, undo or fix it.
- Remember project decisions with `workspace_note`. Stay inside this project: don't bring up the user's personal
  agenda, memories or other conversations unless asked."""


LANG_NAMES = {"pt": "Brazilian Portuguese", "en": "English", "es": "Spanish"}


def build_system() -> str:
    """Stable part of the prompt. Keeping it identical between turns lets Ollama reuse its KV cache
    (identity + rules + profile + tool schemas), so only the new context and message are processed."""
    prof = db.get_profile()
    if workspace.active:
        ws = workspace.active
        return WORKSPACE_IDENTITY.format(name=ws["name"], description=ws["description"] or "-")
    return "\n".join([
        IDENTITY.format(tone=(prof or {}).get("tone", "cordial")),
        f"\n## User profile\n{profile.describe(prof)}",
    ])


# Every context token costs ~12 ms of prompt processing on the reference GPU (~80 tok/s), so each block is only
# sent when the message needs it (v0.6: ~370 -> ~130 tokens for a typical message).
TIME_WORDS = re.compile(
    r"\b(hoje|amanh[aã]|ontem|semana|m[eê]s|dia|hora|horas|minutos?|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|"
    r"domingo|agenda|lembr\w*|marc\w*|agend\w*|reuni\w*|compromiss\w*|evento|prazo|tarefa\w*|pendente\w*|"
    r"today|tomorrow|yesterday|week|month|day|hours?|minutes?|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"schedule\w*|remind\w*|meeting|appointment|event|deadline|tasks?|to-?do|pending|"
    r"hoy|ma[nñ]ana|ayer|lunes|martes|mi[eé]rcoles|jueves|viernes|recu[eé]rd\w*|cita|reuni[oó]n|tareas?|pendientes?|"
    r"\d{1,2}\s?h\b|\d{1,2}:\d{2})\b", re.IGNORECASE)
EXPLICIT_REMEMBER = re.compile(r"\b(lembr[ae]|guard[ae]|memoriz\w*|anot[ae]|remember|note that|recuerda|no olvides|"
                               r"apunta)\b", re.IGNORECASE)
ACTION_REF = re.compile(
    r"\b(cancel\w*|desfa\w*|desfiz|apag\w*|remov\w*|exclu\w*|corrig\w*|alter\w*|mud[ae] (isso|o que)|"
    r"o que (voc[eê] )?(fez|registrou|anotou|salvou|marcou|agendou)|registrou|anotou|salvou|marcou|agendou|"
    r"(o )?[uú]ltim[oa]|isso que|undo|delete|remove|change (that|it)|what did you|you (just )?(logged|saved|added)|"
    r"deshaz|borra\w*|elimina\w*|qu[eé] (hiciste|registraste|guardaste))\b", re.IGNORECASE)
ABOUT_ME = re.compile(r"\b(sobre mim|me conhece|sabe de mim|about me|know me|sobre m[ií]|me conoces|lembra de mim|"
                      r"meu nome|my name|mi nombre)\b", re.IGNORECASE)
KB_CHARS = 650
# AI modes (v0.7). The instruction travels in the per-message context (~40 tokens), NOT in the system prompt:
# changing the system prompt would invalidate the cached prefix and cost ~25 s on the next message.
MODES = {
    "assistant": "",
    "direct": ("MODE DIRECT: give exactly what was asked in the fewest words - usually one or two short sentences, "
               "or a minimal list only if steps are essential. No greetings, no filler, no follow-up questions, no "
               "emojis, no restating the question."),
}
MODES["study"] = (
    "MODE STUDY: act as a patient tutor. Explain step by step with a simple example, check understanding with ONE "
    "short question at the end, adapt to the user's level, prefer the knowledge base and cite it. In quizzes grade "
    "each answer immediately (right/wrong, correct answer, one-line reason).")
DIRECT_MAX_TOKENS = 320  # safety cap for the direct mode (the instruction keeps answers far below it)


def workspace_context(user_text: str) -> str:
    """Workspace turns: only the project (files, notes, recent changes) - never the user's personal data."""
    now = datetime.now()
    parts = [f"## Now\n{now.strftime('%Y-%m-%d %H:%M')}", "\n## Workspace files\n" + workspace.tree_text()]
    notes = workspace.notes()
    if notes:
        parts.append("\n## Project notes\n" + notes)
    recent = workspace.changes(6)
    if recent:
        parts.append("\n## Your latest changes (newest first)\n" + "\n".join(f"- {c['op']} {c['path']}" for c in recent))
    parts.append(f"\nReply ONLY in {LANG_NAMES[detect(user_text) or lang()]}.")
    if MODES.get(settings["ai_mode"]):
        parts.append(MODES[settings["ai_mode"]])
    return "\n".join(parts)


def turn_tools() -> list:
    """Tool schemas for this turn: the workspace has its own file tools plus a few safe general ones."""
    if workspace.active:
        keep = {"search_knowledge", "wikipedia", "get_datetime", "conversation_control"}
        return workspace.SCHEMAS + [x for x in tools.SCHEMAS if x["function"]["name"] in keep]
    # v0.15.5: tools of beta features that are off stay out of the prompt (smaller prompt = faster first answer)
    return [x for x in tools.SCHEMAS if features.tool_allowed(x["function"]["name"])]


def build_context(user_text: str, emergency_topic: str | None = None) -> str:
    """Per-message context, sent right before the user's message. Only what this message needs."""
    if workspace.active and not emergency_topic:
        return workspace_context(user_text)
    now = datetime.now()
    msg_lang = detect(user_text)
    wd = WEEKDAYS[msg_lang or lang()]  # weekday names already in the reply language: small models mistranslate them

    def day(d: datetime) -> str:
        return f"{wd[d.weekday()]} {d.date()}"

    timely = bool(TIME_WORDS.search(user_text))
    parts = [f"## Now\n{day(now)} {now.strftime('%H:%M')}"]
    if timely:
        # v0.15.5: labelled - after a long conversation the model took the 2nd entry of a bare list as "tomorrow"
        parts.append(f"Tomorrow = {day(now + timedelta(days=1))}; day after tomorrow = {day(now + timedelta(days=2))}\n"
                     "Calendar: " + "; ".join(day(now + timedelta(days=d)) for d in range(3, 8)))
    # Memories: the ones related to this message; everything we know only when asked about the user.
    mems = {m["id"]: m for m in memory.recall(user_text, limit=4)}
    if ABOUT_ME.search(user_text):
        for m in memory.recent_memories(12):
            mems.setdefault(m["id"], m)
    if mems:
        parts.append("\n## What you remember about the user\n" + "\n".join(
            f"- [#{m['id']}] {m['content']}" for m in list(mems.values())[:12]))
    # Only what NEXUS did moments ago in this session ("cancel what you just scheduled"); older actions
    # pulled unrelated topics into ambiguous questions (NX-LLM-019).
    recent = max(memory.session_start(), (now - timedelta(minutes=ACTIONS_WINDOW_MIN)).isoformat(timespec="seconds"))
    # v0.15.1: only when the message talks about something NEXUS did - a short reply like "Letra A" (a quiz answer)
    # was matched to "logged 30 reais in books" sitting in this log.
    actions = memory.recent_actions(5, since=recent) if ACTION_REF.search(user_text) else []
    if actions:
        parts.append("\n## Log of your recent actions (history only, NOT appointments)\n" + "\n".join(
            f"- {a['ts'][11:16]} {a['summary']}" for a in actions))
    if timely:
        upcoming, pending = _upcoming(), _pending_tasks()
        parts.append("\n## Upcoming appointments / commitments (next 7 days)\n" + (
            "\n".join(f"- #{e['id']} {day(datetime.fromisoformat(e['start']))} {e['start'][11:16]} {e['title']}"
                      for e in upcoming) or "- nothing scheduled"))
        parts.append("## Pending to-do tasks\n" + (
            "\n".join(f"- #{x['id']} {x['title']}" + (f" (due {x['due']})" if x["due"] else "") for x in pending[:10])
            or "- none"))
    # Short follow-ups ("and for a woman?") carry no keywords: search with the previous question too.
    kb_query = user_text
    if len(user_text.split()) < 6:
        previous_user = next((m["content"] for m in reversed(memory.history(3)) if m["role"] == "user"), "")
        kb_query = f"{previous_user} {user_text}"
    is_action = any(rx.search(user_text) for rx, _, _ in INTENTS)  # "remind me to drink water" needs no book
    hits = [] if is_action else [h for h in knowledge.search(kb_query, limit=3) if h["score"] <= KB_MIN_SCORE]
    hits = [h for h in hits if h["score"] <= hits[0]["score"] * 0.8][:2] if hits else []  # 2nd only if nearly as relevant
    if emergency_topic:  # first-aid follow-up: the exact manual section is always present (NX-LLM-021)
        sec = emergency.section(emergency_topic, msg_lang or lang())
        if sec:
            parts.append(f"\n## {emergency.RULE}\n[{sec['heading']}]\n{sec['content']}")
    elif hits:
        parts.append("\n## Relevant knowledge (local base)\n" + "\n\n".join(
            f"[{h['title']} › {h['heading']}]\n{_clip(h['content'], KB_CHARS)}" for h in hits))
    # v0.16.1: the reply language lives here, not in the system prompt - switching PT/EN/ES changed the whole
    # prompt prefix and the first answer in the new language re-read ~3k tokens (the slow "Hello" in English)
    parts.append(f"\nReply ONLY in {LANG_NAMES[msg_lang or lang()]}.")
    if MODES.get(settings["ai_mode"]):
        parts.append(MODES[settings["ai_mode"]])
    if netprobe.effective() == "online" and settings["integrations"] and not hits:
        # v0.15 auto/online mode with a fast connection: online lookups first when the local base has nothing
        parts.append("Internet is fast right now: for current events or facts the local base doesn't cover, call "
                     "`wikipedia` or `get_news` (they answer in about a second) instead of guessing.")
    parts.append("Requests to store, log, remember, learn, schedule or look up something need the matching tool call.")
    return "\n".join(parts)


def _clip(text: str, limit: int) -> str:
    """Cut at a line/sentence boundary so a knowledge excerpt never ends mid-instruction."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind("\n"), cut.rfind(". "))
    return cut[: end + 1] if end > limit // 2 else cut


# Replies that claim a stored action, or defer a lookup, are only valid after a tool call.
CLAIMED = re.compile(
    r"\b(registrei|anotei|salvei|lembrei|memorizei|aprendi|guardei|adicionei|"
    r"registrou|anotou|salvou|memorizou|aprendeu|guardou|adicionou|ficou (?:salv|registrad|anotad)[oa]|"
    r"(?:it|that)(?:'s| is| has been| was) (?:saved|logged|noted|stored|recorded)|registrad[oa]s?|anotad[oa]|foi salv[oa]|"
    r"aprendid[oa]|memorizad[oa]|i(?:'ve| have)? (?:logged|saved|noted|recorded|stored|remembered|learned|added)|"
    r"registré|anoté|guardé|aprendí|añadí|memoricé|registrad[oa]s?|guardad[oa])\b", re.IGNORECASE)
DEFERRED = re.compile(
    r"(precisaria|preciso|vou|irei) (consultar|verificar|checar|listar)|consultarei|verificarei|"
    r"let me check|i would need to (check|look)|i'll check|necesitar[íi]a (consultar|revisar)|voy a (consultar|revisar)",
    re.IGNORECASE)


# "Salve essa conversa para relatar erros": handled without the model (v0.8 eval: the model also logged the
# report with record_data and answered with a collection id instead of the file).
REPORT_RE = re.compile(r"\b(relat\w* (um |o |os |esse |esses |este )?(erros?|problemas?|bugs?)|report (a |this |the )?"
                       r"(bug|issue|problem|error)s?|report\w* (un |el |los |este )?(error(es)?|problemas?|fallos?)|"
                       r"(salv|guard)\w* (essa|esta|a) conversa)", re.I)

# What the USER asked for -> tools that must have been called this turn (the model sometimes just echoes
# "Aprende que..." without storing anything).
INTENTS = [
    (re.compile(r"^\W*(nexus\W+)?(aprend[aei]|learn( that)?|memorize this|aprende que)\b", re.I),
     {"learn_knowledge", "remember"}, "learn_knowledge"),
    (re.compile(r"^\W*(nexus\W+)?(lembr[ae] que|guard[ae] que|remember that|recuerda que|no olvides que)\b", re.I),
     {"remember", "learn_knowledge"}, "remember"),
    (re.compile(r"^\W*(nexus\W+)?(me lembr[ae] de|remind me|recu[eé]rdame)\b", re.I),
     {"set_reminder", "add_event", "add_task"}, "set_reminder"),
    (re.compile(r"^\W*(nexus\W+)?(registr[ae]|anot[ae]|log|track|record|apunta)\b", re.I),
     {"record_data", "save_note", "add_task", "remember"}, "record_data"),
    (REPORT_RE, {"report_issue"}, "report_issue"),
    # "lê o livro X": v0.15.1 eval - the model answered "Lendo Dom Robo para você" without starting anything
    (re.compile(r"\b(l[eê]|leia|ler|continu[ae] (a )?(ler|leitura)|read|lee|leer)\b.{0,25}\b(livro|book|libro)\b", re.I),
     {"read_book", "list_books"}, "read_book"),
]


# Live data the model cannot know: answering without the tool means refusing ("not available") or, worse,
# inventing headlines/rates (seen in v0.6 tests). Matched anywhere in the message.
LIVE = [
    (re.compile(r"\b(chov\w*|chuva\w*|clima|previs[aã]o do tempo|temperatura|faz(endo)? (frio|calor)|guarda-chuva|"
                r"weather|rain\w*|forecast|temperature|umbrella|llov\w*|lluvia|pron[oó]stico|hace (fr[ií]o|calor))\b", re.I),
     {"get_weather"}, "get_weather"),
    (re.compile(r"\b(not[ií]cias?|manchetes?|news|headlines?|noticias?|titulares)\b", re.I), {"get_news"}, "get_news"),
    (re.compile(r"\b(c[aâ]mbio|cota[cç][aã]o|d[oó]lar(es)?|euros?|libras?|exchange rate|currency|tipo de cambio|"
                r"em reais|in dollars|en pesos)\b", re.I), {"convert_currency"}, "convert_currency"),
]


UI_OPEN_CLAIM = re.compile(r"\b(abri|aberto|aberta|abrindo|abrimos|opened|opening|i've opened|abierto|abierta|abriendo|"
                           r"te levei|levei voc|took you|te llev|vou (te )?(levar|abrir|mostrar)|vamos (abrir|l[aá])|"
                           r"let me (open|take|show)|i'?ll (open|take you|show)|i will (open|take|show)|voy a (abrir|llevar)|"
                           r"te llevo)", re.I)
UI_WORDS = re.compile(r"\b(configura\w*|ajustes|settings|painel|panel|menu|aro|cursor|atalhos?|shortcuts?|atajos?|"
                      r"conversas|conversations|notifica\w*|biblioteca|library|guia|guide|tutorial|interface|interfaz)\b", re.I)


def _needs_tool(reply: str, acted: bool, user_text: str = "", called: set | None = None) -> str | None:
    for rx, expected, tool in LIVE:
        if (rx.search(user_text) and not (called or set()) & expected and settings["integrations"]
                and netprobe.effective() != "offline"):
            return (f"This needs LIVE data that you do not know. Call `{tool}` now; never say it is unavailable and "
                    f"never invent headlines, rates or forecasts. Then answer briefly from the tool result.")
    for rx, expected, tool in INTENTS:
        if rx.search(user_text) and not (called or set()) & expected and features.tool_allowed(tool):
            return (f"The user explicitly asked you to store this, but you did NOT call any tool, so nothing was saved. "
                    f"Call `{tool}` now with the information from the user's message, then confirm briefly in the "
                    f"user's language.")
    # v0.16.5 eval: "Aberto o painel de configurações" without calling the tool - nothing opened
    if "open_interface" not in (called or set()) and UI_OPEN_CLAIM.search(reply) and UI_WORDS.search(user_text + " " + reply):
        return ("You said you opened part of the NEXUS interface but you did NOT call `open_interface`, so nothing "
                "opened. Call `open_interface` now with the right target (and section for settings), then confirm briefly.")
    if not acted and CLAIMED.search(reply):
        return ("You said you stored/recorded something but you did NOT call any tool, so nothing was saved. "
                "Call the correct tool now (record_data, remember, learn_knowledge, add_task, add_event, save_note...), "
                "then confirm briefly in the user's language.")
    if DEFERRED.search(reply):
        return "Don't ask or announce it: call the tool now (e.g. query_data, list_tasks, list_events, search_notes) and answer."
    return None


FILE_CLAIM = re.compile(r"\b(criei|editei|salvei|alterei|atualizei|escrevi|removi|apaguei|created|edited|saved|"
                        r"updated|wrote|deleted|removed|cre[eé]|edit[eé]|guard[eé]|actualic[eé]|borr[eé])\b", re.I)


FILE_PROMISE = re.compile(r"\b(vou (corrigir|ajustar|criar|editar|alterar|atualizar|consertar|implementar)|"
                          r"i('ll| will) (fix|correct|update|create|edit|change|implement)|let me (fix|update|create|edit)|"
                          r"voy a (corregir|arreglar|crear|editar|cambiar|actualizar))\b", re.I)


def _needs_file_tool(reply: str, acted: bool) -> str | None:
    """Workspace safety nets: claiming a file change without a tool call, or ending the turn with a promise
    ("I'll fix it") instead of doing it (seen in the v0.11 evaluation after a failing test)."""
    if not acted and FILE_CLAIM.search(reply):
        return ("You said you changed files but you did NOT call any file tool, so nothing changed. Call write_file / "
                "edit_file / make_folder / delete_file now, then summarize briefly.")
    if FILE_PROMISE.search(reply):
        return "Don't announce it: do it now with the file tools, then summarize what you changed in one or two sentences."
    return None


ATTACH_CHARS = 7000  # ~2k tokens of files per message (the whole prompt must stay inside the 8k context)


def attachment_context(question: str, attachments: list[dict]) -> str:
    """Files attached to this message (v0.15). Small files go in whole; big ones contribute their beginning plus
    the passages that best match the question (word overlap) - no extra AI call, no change to the knowledge base."""
    words = {w for w in re.findall(r"\w{4,}", question.lower())}
    budget = ATTACH_CHARS // max(len(attachments), 1)
    parts = ["## Files attached by the user (read them to answer)"]
    for a in attachments:
        body = a["text"]
        if len(body) > budget:
            head = body[: budget // 3]
            chunks = [body[i:i + 600] for i in range(len(head), len(body), 600)]
            ranked = sorted(chunks, key=lambda c: -len(words & set(re.findall(r"\w{4,}", c.lower()))))
            picked, used = [], len(head)
            for c in ranked:
                if used + len(c) > budget:
                    break
                picked.append(c)
                used += len(c)
            picked.sort(key=body.find)
            body = head + "\n[...]\n" + "\n[...]\n".join(picked) + f"\n[file has {len(a['text'])} characters; excerpts]"
        parts.append(f"### {a['name']}\n{body}")
    return "\n".join(parts)


# v0.15.1 token budget. Measured with qwen3:8b: rules + 34 tool schemas = 3,111 tokens; 12 long exchanges took a
# prompt to 7,746 of 8,192, and a longer conversation overflowed it - Ollama then drops the START of the prompt (the
# rules), so answers came out cut ("d)") and confused (a quiz answer logged as an expense). The history now has to
# fit what is left after the fixed prompt, this turn's context and room for the answer.
ANSWER_RESERVE = 1200          # tokens kept free for the reply
HISTORY_MAX_TOKENS = 2500      # longer histories made answers slow (7k-token prompts: 75-108 s) and confused
OLD_REPLY_CHARS = 1200         # older long answers (news lists, lessons) are shortened in the history


def _looping(text: str) -> bool:
    """A reply that keeps repeating itself: its last 60 characters already appear 3+ times in the last 1,500."""
    tail = text[-60:].strip()
    return len(tail) >= 40 and text[-1500:].count(tail) >= 3


def _trim_loop(text: str) -> str:
    """Keep the reply up to where the repetition starts (the first copy of the repeated part stays)."""
    tail = text[-60:].strip()
    first = text.find(tail)
    second = text.find(tail, first + len(tail)) if first != -1 else -1
    if second <= 0:
        return text.rstrip() + " …"
    cut = max(text.rfind(p, 0, second) for p in (". ", "! ", "? ", "\n"))  # end at a whole sentence
    return text[: cut + 1 if cut > 0 else second].rstrip()


def est_tokens(text: str) -> int:
    """Conservative estimate (pt/en/es prose ~3.3 chars per token; JSON packs a bit more)."""
    return int(len(text) / 2.8) + 4  # calibrated: a 7,290-token prompt was estimated low with 3.3


_anchors: dict = {}  # conversation -> id of the first message the model still sees (ids are unique; times tie)
WINDOW_REFILL = 0.55  # after a jump, the window keeps this share of its limits (room to grow again)


def _history_messages(extra_tokens: int = 0) -> list[dict]:
    """The open conversation's recent exchanges that fit the context. The window does NOT slide one message per
    turn: that changed the start of the prompt every time, so Ollama's cache never hit and long conversations paid
    ~40 s per answer (v0.15.1 eval). It stays anchored and, when it gets full, jumps ahead to the newest ~half -
    the prompt prefix then stays identical for several turns. Long answers are shortened the same way every turn
    (also for stability)."""
    rows = memory.history(200)
    fixed = est_tokens(build_system()) + int(len(json.dumps(turn_tools(), ensure_ascii=False)) / 4.5)
    budget = min(HISTORY_MAX_TOKENS, int(settings["llm_context"]) - fixed - extra_tokens - ANSWER_RESERVE)
    max_msgs = int(settings["history_turns"]) * 2
    items = []
    for m in rows:
        content = m["content"]
        if m["role"] == "assistant" and len(content) > OLD_REPLY_CHARS:
            content = content[:OLD_REPLY_CHARS] + " […]"
        items.append({"role": m["role"], "content": content, "id": m.get("id", 0), "cost": est_tokens(content)})
    key = "temp" if memory.temporary else memory.current_conversation()
    anchor = _anchors.get(key)
    if anchor is not None and not any(m["id"] == anchor for m in items):
        anchor = None  # history cleared / temporary chat restarted: start over instead of sending nothing
    window = [m for m in items if anchor is None or m["id"] >= anchor]
    if len(window) > max_msgs or sum(m["cost"] for m in window) > budget:
        keep, used = [], 0
        for m in reversed(items):
            if len(keep) >= max(2, int(max_msgs * WINDOW_REFILL)) or used + m["cost"] > budget * WINDOW_REFILL:
                break
            keep.insert(0, m)
            used += m["cost"]
        if not keep and items:  # a single huge message: send just the newest one
            keep = items[-1:]
        window = keep
    while window and window[0]["role"] == "assistant":  # never start with an answer whose question was dropped
        window.pop(0)
    if window:
        _anchors[key] = window[0]["id"]
    return [{"role": m["role"], "content": m["content"]} for m in window]


def side_messages(instruction: str) -> list[dict]:
    """Background jobs (title, memory extraction) reuse the conversation's exact prompt prefix - rules, tool schemas
    and history - and only add their request at the end. Ollama keeps ONE prompt cache: a job with a different
    prompt evicted it and the user's next message re-read ~5k tokens (measured 38.5 s instead of ~2 s, v0.15.1)."""
    request = "(Internal request from NEXUS itself, not from the user. Do not call tools.)\n" + instruction
    return [{"role": "system", "content": build_system()}, *_history_messages(est_tokens(request)),
            {"role": "user", "content": request}]


def warm_up() -> dict:
    """Run during the boot animation: load the model and cache the fixed prompt prefix (system + tools)."""
    return llm.prefill([{"role": "system", "content": build_system()}, *_history_messages(),
                        {"role": "user", "content": "ok"}], turn_tools())


def last_reply() -> str:
    """Last answer of the open conversation (temporary chats included)."""
    return next((m["content"] for m in reversed(memory.history(50)) if m["role"] == "assistant" and m["content"]), "")


class Assistant:
    def __init__(self, emit, control_hook=lambda action: None, confirm_hook=lambda command: False):
        self.emit = emit  # emit(event: str, payload) -> pushes to the UI
        self.control_hook = control_hook  # executes pause/resume/stop on the speaker
        self.confirm_hook = confirm_hook  # asks the user to allow a workspace command (blocks; returns bool)
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.emergencies = emergency.Tracker()

    def ask(self, text: str, spoken: bool = False, attachments: list | None = None):
        """Handle one user message (blocking; call from a worker thread). attachments: [{"name", "text"}]."""
        text = text.strip()
        if not text:
            return
        with self.lock:
            self.cancel.clear()
            self.attachments = attachments or []
            self._ask(text, spoken)

    def interrupt(self):
        """Stop the generation in progress (closing the stream also stops Ollama)."""
        self.cancel.set()

    def _ask(self, text, spoken):
        topic = emergency.detect(text)
        if topic and self.emergencies.first_time(topic):
            # Emergency: answer instantly with the manual's protocol; never wait for or trust the model here.
            reply = emergency.protocol_reply(topic, detect(text) or lang())
            self.emergencies.mark(topic)
            memory.add_message("user", text)
            memory.add_message("assistant", reply)
            self.emit("tool", {"name": "emergency", "args": {"topic": topic}})
            self._level_up(text, {"emergency"}, spoken)
            self.emit("done", {"text": reply, "speak": True, "interrupted": False})
            return
        if REPORT_RE.search(text):
            memory.add_message("user", text)
            result = tools.report_issue(text)
            reply = t("report_saved", file=result["file"])
            memory.add_message("assistant", reply)
            self.emit("tool", {"name": "report_issue", "args": {}})
            self.emit("done", {"text": reply, "speak": True, "interrupted": False})
            return
        nav = ui_nav.detect(text)
        if nav and tools.ui_hook:  # v0.16.5: "abre as configurações", "quero mudar a cor do aro" - instant, no model
            nav, reply = ui_nav.reply(nav)
            tools.ui_hook({**nav, "say": reply})
            self.emit("tool", {"name": "open_interface", "args": nav})
            self.emit("done", {"text": reply, "speak": nav["target"] != "tutorial", "interrupted": False})
            return
        # Context travels inside the current user turn (many chat templates drop extra system messages); the history
        # keeps only the raw text. v0.15.5 measured keeping the context blocks too: the knowledge excerpts fill the
        # history window, it jumps more often and answers got slower (14.9 s vs 13.5 s over 16 questions).
        context = build_context(text, emergency_topic=topic)
        if getattr(self, "attachments", None):
            context += "\n" + attachment_context(text, self.attachments)
            names = ", ".join(a["name"] for a in self.attachments)
            text_for_history = f"{text}\n[{names}]"
        else:
            text_for_history = text
        turn = f"<context>\n{context}\n</context>\n\n{text}"
        messages = [{"role": "system", "content": build_system()}, *_history_messages(est_tokens(turn)),
                    {"role": "user", "content": turn}]
        previous = last_reply()
        memory.add_message("user", text_for_history)
        reply, changed, nudged, finished, round_text, called = "", False, False, False, "", set()
        kept = ""  # real answer text written before a tool call: stays on screen and in the reply (v0.12)
        used: set = set()  # every tool that ran this turn (skills XP)
        try:
            schemas = turn_tools()
            for _ in range(MAX_WORKSPACE_ROUNDS if workspace.active else MAX_TOOL_ROUNDS):
                round_text, calls = "", None
                cap = DIRECT_MAX_TOKENS if settings["ai_mode"] == "direct" else ANSWER_RESERVE
                for kind, value in llm.stream_chat(messages, schemas, max_tokens=cap):
                    if self.cancel.is_set():
                        break
                    if kind == "token":
                        round_text += value
                        if len(round_text) > 600 and len(round_text) % 40 < len(value) and _looping(round_text):
                            round_text = _trim_loop(round_text)
                            break  # the model fell into a loop (v0.15.1 eval: a joke repeated for 43 minutes)
                        if not topic:  # first-aid follow-ups are checked (emergency.guard) before being shown
                            self.emit("token", value)
                    elif kind == "tool_calls":
                        calls = value
                if _looping(round_text):  # short loops end before the in-stream check runs
                    round_text = _trim_loop(round_text)
                if self.cancel.is_set():
                    reply = round_text
                    break
                if not calls:
                    nudge = None if nudged else (_needs_file_tool(round_text, changed) if workspace.active
                                                 else _needs_tool(round_text, changed, text, called))
                    if nudge:  # the model claimed/deferred an action without calling a tool: ask again once
                        nudged = True
                        self.emit("reset", {"keep": kept})
                        messages += [{"role": "assistant", "content": round_text}, {"role": "user", "content": nudge}]
                        continue
                    reply = round_text
                    break
                # A short line before a tool call ("let me check...") is narration and is removed; a real answer
                # (the user already read/heard it) stays - v0.11 wiped a whole JS lesson from the screen while the
                # voice kept reading it.
                if len(round_text.strip()) >= NARRATION_MAX:
                    kept += round_text.strip() + "\n\n"
                    self.emit("token", "\n\n")
                elif round_text:
                    self.emit("reset", {"keep": kept})
                for c in calls:
                    c["id"] = c["id"] or f"call_{uuid.uuid4().hex[:8]}"
                messages.append({"role": "assistant", "content": "", "tool_calls": [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                    for c in calls]})
                for c in calls:
                    try:
                        args = json.loads(c["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    self.emit("tool", {"name": c["name"], "args": args})
                    used.add(c["name"])
                    if c["name"] == "conversation_control":
                        result, final = self._control(str(args.get("action", "")), previous)
                        if final is not None:  # pause/stop/resume/repeat end the turn without another model round
                            reply, finished = final, True
                    else:
                        if workspace.active and c["name"] in workspace.FILE_TOOLS:
                            result = workspace.execute(c["name"], args, ask=self.confirm_hook)
                            changed |= c["name"] in workspace.MUTATING
                        elif memory.temporary and c["name"] == "remember" and not EXPLICIT_REMEMBER.search(text):
                            # temporary chat: nothing is memorized unless the user explicitly asks (v0.15.1 eval:
                            # "I have a turtle called Jorge" was saved by the model on its own)
                            result = {"skipped": "temporary chat - facts are only saved when the user asks to"}
                        else:
                            result = tools.execute(c["name"], args)
                            changed |= c["name"] in tools.MUTATING
                        called.add(c["name"])
                    messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"],
                                     "content": json.dumps(result, ensure_ascii=False, default=str)[:6000]})
                if finished:
                    break
        except llm.LLMOffline as exc:
            from .logs import log

            detail = str(exc.detail).replace(settings["llm_api_key"], "***") if settings["llm_api_key"] else exc.detail
            log.warning(f"AI request failed: kind={exc.kind} status={exc.status} server={llm._base()} "
                        f"model={settings['llm_model']} detail={detail[:300]}")
            self.emit("error", {"message": t("llm_err_" + exc.kind, model=settings["llm_model"]), "detail": detail[:300],
                                "kind": exc.kind})
            return
        interrupted = self.cancel.is_set()
        reply = (reply or ("" if finished or interrupted else round_text)).strip()
        if kept and not finished:
            reply = (kept + reply).strip()
        if topic and reply:
            reply = emergency.guard(topic, reply, detect(text) or lang())
        if reply:
            memory.add_message("assistant", reply)
        self.emit("done", {"text": reply, "speak": bool(reply) and not interrupted, "interrupted": interrupted})
        if reply and not interrupted and not memory.temporary:
            self._level_up(text, used, spoken)
        if changed:
            self.emit("refresh", None)
        # Automatic memory: only self-statements, never in emergencies or temporary conversations, and not when
        # the model already called `remember` this turn (no second LLM pass).
        if (settings["auto_memory"] and reply and not finished and not topic and "remember" not in called
                and not memory.temporary and not workspace.active and memory.states_fact(text)):
            threading.Thread(target=self._extract_memories, args=(text, reply), daemon=True).start()
        cid = memory.current_conversation()
        if reply and not interrupted and cid and not memory.temporary and settings["auto_title"] and not workspace.active:
            threading.Thread(target=self._title_conversation, args=(cid,), daemon=True).start()

    def _title_conversation(self, cid: int):
        """Title + one-line description for the conversations panel, written by the model in the background:
        after the first answer and again (final) after the 4th exchange, when the topic is clearer."""
        row = db.one("SELECT titled_at, (SELECT COUNT(*) FROM messages WHERE conversation_id = ?) AS n "
                     "FROM conversations WHERE id = ?", (cid, cid))
        if not row or row["titled_at"] == -1 or not (row["n"] >= 2 and row["titled_at"] == 0 or row["n"] >= 8):
            return
        final = row["n"] >= 8
        prompt = ("Give the conversation above a short title (max 6 words) and a one-sentence description of what "
                  'it is about, in its language. Answer ONLY with JSON {"title": str, "description": str}.')
        try:
            out = llm.complete(side_messages(prompt), tools=turn_tools(), max_tokens=120)
            data = json.loads(re.search(r"\{.*\}", out, re.DOTALL).group(0))
            title = str(data.get("title", "")).strip().strip('"')
        except Exception:
            return
        if title:
            memory.set_conversation_title(cid, title, str(data.get("description", "")), final=final)
            self.emit("conversations", None)

    def _level_up(self, text, used, spoken=False):
        """Skills XP for the finished turn (v0.13); a level-up shows a toast in the interface."""
        if not features.enabled("skills"):
            return
        try:
            ups = skills.award(text, used, spoken=spoken, workspace=bool(workspace.active),
                               study=settings["ai_mode"] == "study")
        except Exception:
            return
        if ups:
            self.emit("levelup", ups)

    def _control(self, action: str, previous: str):
        """conversation_control chosen by the model. Returns (tool result, final reply or None)."""
        if action in ("pause", "resume", "stop"):
            self.control_hook(action)
            return {"ok": True}, ""
        if action == "repeat":
            return {"ok": True}, f"{t('repeat_intro')} {previous}" if previous else t("nothing_to_repeat")
        if action == "clearer":
            return {"instruction": "Explain your previous answer again, more clearly and simply, with short "
                                   "sentences. Start with: " + t("clearer_intro"),
                    "previous_answer": previous}, None
        return {"error": f"unknown action {action}"}, None

    def _extract_memories(self, user_text, reply):
        """Background pass that saves durable facts the model didn't explicitly store."""
        # Only the user's own words: summarising the assistant's answer turned topics into fake "interests"
        # ("the user is interested in CPR") - NX-LLM-016.
        prompt = (
            "Below is ONE message written by the user. Extract only durable facts the user EXPLICITLY STATED about "
            "THEMSELVES (preferences, people in their life, habits, goals, health conditions, work). "
            "Questions, requests and the topics they ask about are NOT facts: never infer interests, needs or goals "
            "from them. Temporary situations are not facts. Write each fact as a short sentence in the user's language. "
            'Answer ONLY with a JSON array of objects {"fact": str, "category": str}, or [] if nothing (most messages).\n\n'
            f"USER MESSAGE: {user_text}"
        )
        try:
            out = llm.complete(side_messages(prompt), tools=turn_tools(), max_tokens=200)  # keeps the prompt cache
            match = re.search(r"\[.*\]", out, re.DOTALL)
            facts = json.loads(match.group(0)) if match else []
        except Exception:
            return
        saved = False
        for f in facts[:3]:
            if isinstance(f, dict) and f.get("fact"):
                saved |= bool(memory.remember(f["fact"], f.get("category") or "geral", source="auto"))
        if saved:
            self.emit("refresh", None)


def greeting() -> str:
    """Opening line, instant (no LLM):
    - no profile yet          -> NEXUS introduces itself and asks for the profile
    - first time with profile -> full introduction using the user's name
    - user asked to be reminded next time (remind_next_session) -> "shall we continue <topic>?"
    - otherwise               -> "Hello <name>, what do we have for today?"
    Greetings that the user may answer ("yes") are stored in the history so the model has context."""
    prof = db.get_profile()
    if not prof:
        return t("intro_anon")
    name = prof["name"].split()[0]
    if db.get_state("introduced") != "1":
        db.set_state("introduced", "1")
        text = t("intro", name=name)
    else:
        notes = db.all("SELECT id, topic FROM session_notes WHERE delivered IS NULL ORDER BY id")
        if notes:
            topics = [n["topic"] for n in notes]
            joined = topics[0] if len(topics) == 1 else f"{', '.join(topics[:-1])} {t('and')} {topics[-1]}"
            text = t("continue", name=name, topics=joined)
            db.execute(f"UPDATE session_notes SET delivered = ? WHERE id IN ({','.join('?' * len(notes))})",
                       (datetime.now().isoformat(timespec="seconds"), *[n["id"] for n in notes]))
        else:
            text = t("hello", name=name)
    memory.add_message("assistant", text)
    return text
