"""The NEXUS brain: builds context, runs the model with tools and keeps memory up to date."""
import json
import re
import threading
import uuid
from datetime import datetime, timedelta

from . import emergency, knowledge, llm, memory, profile, tools
from .config import settings
from .db import db
from .i18n import WEEKDAYS, detect, lang, t

MAX_TOOL_ROUNDS = 6
KB_MIN_SCORE = -7.5  # calibrated on the seed books: real matches score below this, noise above
ACTIONS_WINDOW_MIN = 15

IDENTITY = """You are N.E.X.U.S (Networked Experiential Intelligence & User System), a personal AI assistant
inspired by J.A.R.V.I.S, running locally on the user's computer. You remember the user, manage their tasks,
schedule, notes and data, solve problems and act in real time through your tools.

Rules:
- {reply_lang} You understand Portuguese, English and Spanish.
- Tone: {tone}. Be concise and natural: replies are often spoken aloud, so avoid long lists, tables and code unless asked.
- ACTIONS REQUIRE TOOL CALLS. Saying you did something without calling the tool is a lie and is forbidden:
  log money/expenses/any measurement -> `record_data` (collection e.g. "gastos"/"expenses", one call per item);
  totals or "how much" questions -> `query_data` then add the numbers yourself;
  durable facts about the user (allergies, preferences, people, habits) -> `remember`;
  "learn/aprenda/aprende" -> `learn_knowledge`; reminders -> `set_reminder`; appointments -> `add_event`; to-dos -> `add_task`.
- Resolve relative dates with the calendar below; never compute weekdays yourself. Use ISO datetimes.
- Never show JSON, tool names or internal steps to the user; just give the final answer.
- Questions about agenda, schedule, commitments or pending items: answer from BOTH the "Upcoming
  appointments" and "Pending to-do tasks" context sections; appointments are commitments too. List every item.
- Never show internal ids (#12) to the user; ids are only for tool calls.
- Short or elliptical follow-ups ("and for a woman?", "tell me the exact values", "why?") refer to YOUR LAST ANSWER
  and the user's last question, never to older topics, memories or the action log.
- Numbers and facts: give the typical average and the usual range. If there is no single exact value (body
  measurements, prices, populations...), say so clearly. Stay consistent with what you already said; if you
  were wrong, correct yourself explicitly ("Correcting: ..."). Never invent precision.
- Requests about your own speech -> call `conversation_control`: repeat what you said ("repeat"), the user didn't
  understand ("clearer"), wait/hold on ("pause"), go on ("resume"), be quiet ("stop").
- For factual questions (first aid, philosophy, finance, programming, health, productivity...) prefer the knowledge base;
  cite the source name briefly. In medical emergencies always tell them to call emergency services first (Brazil: SAMU 192 / Bombeiros 193; US: 911; Spain/EU: 112).
- Never invent stored data: read it with tools."""


def _upcoming(days=7):
    start = datetime.now().replace(hour=0, minute=0)
    return tools.list_events(start.isoformat(timespec="minutes"),
                             (start + timedelta(days=days)).isoformat(timespec="minutes"))


def _pending_tasks():
    return tools.list_tasks("pending")


def build_system() -> str:
    """Stable part of the prompt. Keeping it identical between turns lets Ollama reuse its KV cache
    (identity + rules + profile + tool schemas), so only the new context and message are processed."""
    prof = db.get_profile()
    return "\n".join([
        IDENTITY.format(reply_lang=t("reply_lang"), tone=(prof or {}).get("tone", "cordial")),
        f"\n## User profile\n{profile.describe(prof)}",
    ])


def build_context(user_text: str, emergency_topic: str | None = None) -> str:
    """Per-message context, sent right before the user's message."""
    now = datetime.now()
    msg_lang = detect(user_text)
    wd = WEEKDAYS[msg_lang or lang()]  # weekday names already in the reply language: small models mistranslate them

    def day(d: datetime) -> str:
        return f"{wd[d.weekday()]} {d.date()}"

    parts = [
        f"## Now\n{day(now)} {now.strftime('%H:%M')}",
        "Calendar: " + "; ".join(day(now + timedelta(days=d)) for d in range(8)),
    ]
    mems = {m["id"]: m for m in memory.recall(user_text)}
    for m in memory.recent_memories(6):
        mems.setdefault(m["id"], m)
    if mems:
        parts.append("\n## What you remember about the user\n" + "\n".join(
            f"- [#{m['id']}] {m['content']}" for m in list(mems.values())[:12]))
    # Only what NEXUS did moments ago in this session ("cancel what you just scheduled"); older actions
    # pulled unrelated topics into ambiguous questions (NX-LLM-019).
    recent = max(memory.session_start(), (now - timedelta(minutes=ACTIONS_WINDOW_MIN)).isoformat(timespec="seconds"))
    actions = memory.recent_actions(5, since=recent)
    if actions:
        parts.append("\n## Log of your recent actions (history only, NOT appointments)\n" + "\n".join(f"- {a['ts'][:16]} {a['summary']}" for a in actions))
    upcoming, pending = _upcoming(), _pending_tasks()
    parts.append("\n## Upcoming appointments / commitments (next 7 days)\n" + (
        "\n".join(f"- #{e['id']} {day(datetime.fromisoformat(e['start']))} {e['start'][11:16]} {e['title']}"
                  for e in upcoming) or "- nothing scheduled"))
    parts.append("## Pending to-do tasks\n" + (
        "\n".join(f"- #{x['id']} {x['title']}" + (f" (due {x['due']})" if x["due"] else "") for x in pending[:10])
        or "- none"))
    # Only inject knowledge that clearly matches (BM25: more negative = better). Every token here costs
    # prompt-processing time on each turn; the model can still call search_knowledge on its own.
    # Short follow-ups ("and for a woman?") carry no keywords: search with the previous question too.
    kb_query = user_text
    if len(user_text.split()) < 6:
        previous_user = next((m["content"] for m in reversed(memory.history(3)) if m["role"] == "user"), "")
        kb_query = f"{previous_user} {user_text}"
    hits = [h for h in knowledge.search(kb_query, limit=3) if h["score"] <= KB_MIN_SCORE]
    hits = [h for h in hits if h["score"] <= hits[0]["score"] * 0.6][:2] if hits else []
    if emergency_topic:  # first-aid follow-up: the exact manual section is always present (NX-LLM-021)
        sec = emergency.section(emergency_topic, msg_lang or lang())
        if sec:
            parts.append(f"\n## {emergency.RULE}\n[{sec['heading']}]\n{sec['content']}")
    elif hits:
        parts.append("\n## Possibly relevant knowledge (local base)\n" + "\n\n".join(
            f"[{h['title']} › {h['heading']}]\n{h['content'][:900]}" for h in hits))
    if msg_lang:
        name = {"pt": "Brazilian Portuguese", "en": "English", "es": "Spanish"}[msg_lang]
        parts.append(f"\n## Language\nThe user's message is in {name}. Reply ONLY in {name}.")
    parts.append("\nIf the message below asks you to store, log, remember, learn, schedule or look up "
                 "something, call the matching tool before answering. Answer the message below the context.")
    return "\n".join(parts)


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
]


def _needs_tool(reply: str, acted: bool, user_text: str = "", called: set | None = None) -> str | None:
    for rx, expected, tool in INTENTS:
        if rx.search(user_text) and not (called or set()) & expected:
            return (f"The user explicitly asked you to store this, but you did NOT call any tool, so nothing was saved. "
                    f"Call `{tool}` now with the information from the user's message, then confirm briefly in the "
                    f"user's language.")
    if not acted and CLAIMED.search(reply):
        return ("You said you stored/recorded something but you did NOT call any tool, so nothing was saved. "
                "Call the correct tool now (record_data, remember, learn_knowledge, add_task, add_event, save_note...), "
                "then confirm briefly in the user's language.")
    if DEFERRED.search(reply):
        return "Don't ask or announce it: call the tool now (e.g. query_data, list_tasks, list_events, search_notes) and answer."
    return None


def _history_messages():
    return [{"role": m["role"], "content": m["content"]} for m in memory.history(settings["history_turns"])]


def last_reply() -> str:
    row = db.one("SELECT content FROM messages WHERE role = 'assistant' AND content != '' ORDER BY id DESC LIMIT 1")
    return row["content"] if row else ""


class Assistant:
    def __init__(self, emit, control_hook=lambda action: None):
        self.emit = emit  # emit(event: str, payload) -> pushes to the UI
        self.control_hook = control_hook  # executes pause/resume/stop on the speaker
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.emergencies = emergency.Tracker()

    def ask(self, text: str, spoken: bool = False):
        """Handle one user message (blocking; call from a worker thread)."""
        text = text.strip()
        if not text:
            return
        with self.lock:
            self.cancel.clear()
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
            self.emit("done", {"text": reply, "speak": True, "interrupted": False})
            return
        # Context travels inside the current user turn (many chat templates drop extra system messages);
        # history keeps only the raw text, so the cached prompt prefix stays valid on the next turn.
        context = build_context(text, emergency_topic=topic)
        messages = [{"role": "system", "content": build_system()}, *_history_messages(),
                    {"role": "user", "content": f"<context>\n{context}\n</context>\n\n{text}"}]
        previous = last_reply()
        memory.add_message("user", text)
        reply, changed, nudged, finished, round_text, called = "", False, False, False, "", set()
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                round_text, calls = "", None
                for kind, value in llm.stream_chat(messages, tools.SCHEMAS):
                    if self.cancel.is_set():
                        break
                    if kind == "token":
                        round_text += value
                        self.emit("token", value)
                    elif kind == "tool_calls":
                        calls = value
                if self.cancel.is_set():
                    reply = round_text
                    break
                if not calls:
                    nudge = None if nudged else _needs_tool(round_text, changed, text, called)
                    if nudge:  # the model claimed/deferred an action without calling a tool: ask again once
                        nudged = True
                        self.emit("reset", None)
                        messages += [{"role": "assistant", "content": round_text}, {"role": "user", "content": nudge}]
                        continue
                    reply = round_text
                    break
                if round_text:  # narration before a tool call ("let me check...") is not part of the answer
                    self.emit("reset", None)
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
                    if c["name"] == "conversation_control":
                        result, final = self._control(str(args.get("action", "")), previous)
                        if final is not None:  # pause/stop/resume/repeat end the turn without another model round
                            reply, finished = final, True
                    else:
                        result = tools.execute(c["name"], args)
                        changed |= c["name"] in tools.MUTATING
                        called.add(c["name"])
                    messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"],
                                     "content": json.dumps(result, ensure_ascii=False, default=str)[:6000]})
                if finished:
                    break
        except llm.LLMOffline as exc:
            self.emit("error", {"message": t("llm_offline"), "detail": str(exc)})
            return
        interrupted = self.cancel.is_set()
        reply = (reply or ("" if finished or interrupted else round_text)).strip()
        if reply:
            memory.add_message("assistant", reply)
        self.emit("done", {"text": reply, "speak": bool(reply) and not interrupted, "interrupted": interrupted})
        if changed:
            self.emit("refresh", None)
        if settings["auto_memory"] and reply and not finished and not topic and memory.states_fact(text):
            threading.Thread(target=self._extract_memories, args=(text, reply), daemon=True).start()

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
            out = llm.complete([{"role": "user", "content": prompt}])
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
