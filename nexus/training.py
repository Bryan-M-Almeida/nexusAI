"""Training mode (beta, v0.17.5).

While a session is active the user teaches NEXUS by talking normally; every statement is kept as a lesson and NEXUS
notes it instantly (no model call; questions still go to the AI). When the user finishes, NEXUS:
  1. splits the lessons into facts (no model call), separating facts about the user (personal) from general knowledge;
  2. looks for evidence for each general fact: the local knowledge base and, when online, Wikipedia;
  3. asks the model to judge every fact against its evidence (one call): agree / disagree / unknown;
  4. keeps what was confirmed (knowledge base, category "Aprendizados") and the personal facts (memories), and leaves
     out what was contradicted or couldn't be checked;
  5. records the session (score = % confirmed among the facts that could be compared) for the "Aprendizados" tab.
The ring shows the analysis like the voice download: waving rings and the percentage in the core."""
import json
import re
from datetime import datetime

from . import i18n, knowledge, llm, memory, netprobe
from .config import settings
from .db import db

db.execute("""CREATE TABLE IF NOT EXISTS trainings (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL DEFAULT '',
    started TEXT NOT NULL,
    finished TEXT,
    score REAL,
    lessons TEXT NOT NULL DEFAULT '[]',
    facts TEXT NOT NULL DEFAULT '[]'
)""")

session: dict = {"active": False, "id": None, "topic": "", "lessons": []}
MAX_FACTS = 12

START_RX = re.compile(r"^\W*(nexus\W+)?((vamos )?(come[cç]a[r]?|inicia[r]?|abr[ea]|ativa[r]?|liga[r]?|entra[r]? n[oa]|modo)\s+(o |a |um |uma |no )?"
                      r"(modo\s+)?(treino|treinamento)|(start|begin|enter)\s+(a\s+|the\s+)?training( mode)?|training mode|"
                      r"(empieza|empezar|inicia|iniciar|activa)\s+(el\s+|un\s+|modo\s+)?entrenamiento|modo entrenamiento)\b(.*)$", re.I)
FINISH_RX = re.compile(r"^\W*(nexus\W+)?((termin[ae]r?|finaliz[ae]r?|encerr[ae]r?|acab[aeo]u?|par[ae]r?|sai[ar]? d[oa])\s+(o |a |do |da )?"
                       r"(modo\s+)?(treino|treinamento)|analis[ae]r? o que (voc[eê] )?aprendeu|"
                       r"(finish|end|stop)\s+(the\s+)?training|analy[sz]e what you learned|"
                       r"(termina|terminar|finaliza|acaba)\s+(el\s+)?entrenamiento|analiza lo que aprendiste)\b", re.I)


def detect(text: str) -> tuple[str, str] | None:
    """("start", topic) / ("finish", "") for the training commands; else None."""
    if FINISH_RX.search(text.strip()):
        return ("finish", "")
    m = START_RX.search(text.strip())
    if m:
        rest = (m.group(m.lastindex) or "").strip(" .!?")
        topic = re.sub(r"^(sobre|about|de|on|acerca de)\s+", "", rest, flags=re.I).strip(" .!?")
        return ("start", topic[:80])
    return None


def start(topic: str = "") -> dict:
    sid = db.execute("INSERT INTO trainings(topic, started) VALUES (?, ?)",
                     (topic, datetime.now().isoformat(timespec="seconds"))).lastrowid
    session.update(active=True, id=sid, topic=topic, lessons=[])
    db.log_action("treinamento", f"Iniciou um treinamento{': ' + topic if topic else ''}")
    return state()


def add_lesson(text: str):
    if session["active"] and text.strip():
        session["lessons"].append(text.strip())
        db.execute("UPDATE trainings SET lessons = ? WHERE id = ?", (json.dumps(session["lessons"], ensure_ascii=False), session["id"]))


def state() -> dict:
    return {"active": session["active"], "id": session["id"], "topic": session["topic"], "lessons": len(session["lessons"])}


CONTEXT = ("TRAINING MODE: the user is teaching you. Do NOT lecture, correct or add facts of your own. Reply in ONE short "
           "sentence saying what you understood (or ask ONE short question if something is unclear). Never ask whether "
           "to save it and never call storage tools (remember, learn_knowledge, record_data, save_note): everything "
           "taught is checked and saved automatically when the user finishes the training.")


def _json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\[.*\]", text, flags=re.S)
    return json.loads(m.group(0)) if m else []


# Each statement the user taught is a fact (no model call: asked to "extract the facts the user taught", qwen3 kept
# only the facts about the user and dropped every general one). Questions, greetings and commands are skipped.
PERSONAL = re.compile(r"\b(eu|meu|minha|meus|minhas|mim|comigo|i|my|mine|me|myself|yo|mi|mis|conmigo)\b", re.I)
SKIP = re.compile(r"^\W*(oi|ol[aá]|ok|okay|obrigad|valeu|thanks?|thank you|hola|gracias|beleza|certo|entendeu|nexus)\b", re.I)


def extract_facts(lessons: list[str]) -> list[dict]:
    facts, seen = [], set()
    for lesson in lessons:
        for sentence in re.split(r"(?<=[.!;])\s+|\n+", lesson):
            s = sentence.strip(" -•*\t")
            if len(s) < 12 or s.endswith("?") or SKIP.match(s) or s.lower() in seen:
                continue
            seen.add(s.lower())
            facts.append({"fact": s if s[-1] in ".!" else s + ".", "personal": bool(PERSONAL.search(s))})
    return facts[-MAX_FACTS:]  # the most recent ones when the session was long


def _wiki(fact: str) -> tuple[str, str]:
    """Full-text Wikipedia search for the whole sentence (the title search used by the wikipedia tool finds nothing
    for a sentence): the summaries of the two best articles."""
    from urllib.parse import quote

    from .i18n import lang
    from .integrations import _get

    code = lang()
    found = _get(f"https://{code}.wikipedia.org/w/api.php", action="query", list="search", srsearch=fact[:200],
                 srlimit=2, format="json").json().get("query", {}).get("search", [])
    texts, url = [], ""
    for hit in found:
        page = _get(f"https://{code}.wikipedia.org/api/rest_v1/page/summary/{quote(hit['title'].replace(' ', '_'))}").json()
        if page.get("extract"):
            texts.append(f"{page.get('title', hit['title'])}: {page['extract'][:520]}")
            url = url or page.get("content_urls", {}).get("desktop", {}).get("page", "")
    return "\n".join(texts), url


def online_allowed() -> bool:
    from . import legal

    return legal.accepted() and netprobe.effective() != "offline" and bool(settings.get("integrations", True))


def evidence(fact: str) -> dict:
    hits = knowledge.search(fact, limit=1)
    local = f"{hits[0]['heading']}: {hits[0]['content'][:500]}" if hits else ""
    online, source = "", ""
    if online_allowed():
        try:
            online, source = _wiki(fact)
        except Exception:  # no connection / service down: the fact is judged with what is left
            pass
    return {"local": local, "online": online, "source": source}


def judge(items: list[dict]) -> list[dict]:
    blocks = []
    for i, it in enumerate(items, 1):
        ev = it["evidence"]
        blocks.append(f"{i}. FACT: {it['fact']}\n   EVIDENCE (online): {ev['online'] or '-'}\n   EVIDENCE (local): {ev['local'] or '-'}")
    prompt = ("You are a careful fact-checker. Judge each FACT using its EVIDENCE first. Return ONLY a JSON array with one "
              "item per fact: {\"i\": number, \"verdict\": \"agree\" | \"disagree\" | \"unknown\", \"note\": \"at most "
              "12 words, in the fact's language\"}.\n"
              "- agree: the evidence (or certain, basic common knowledge) supports the fact; approximate numbers count "
              "(\"about 27 days\" agrees with 27.3 days).\n"
              "- disagree: the evidence clearly contradicts it; the note says what is correct, copied from the evidence.\n"
              "- unknown: no evidence about it and you are not certain. Never guess.\n\n" + "\n".join(blocks))
    out = llm.complete([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=900)
    verdicts = {int(v.get("i", 0)): v for v in _json(out) if isinstance(v, dict)}
    for i, it in enumerate(items, 1):
        v = verdicts.get(i, {})
        it["verdict"] = v.get("verdict") if v.get("verdict") in ("agree", "disagree", "unknown") else "unknown"
        it["note"] = str(v.get("note", ""))[:120]
    return items


def _title(text: str) -> str:
    words = re.sub(r"[^\w\s-]", "", text).split()
    return " ".join(words[:8])[:70] or "Aprendizado"


def finish(progress=lambda pct: None) -> dict:
    """Analyze, keep what was confirmed and record the session. progress(0..100) drives the ring."""
    if not session["active"]:
        return {"ok": False, "error": "no training"}
    sid, topic, lessons = session["id"], session["topic"], list(session["lessons"])
    session.update(active=False)
    progress(3)
    facts = extract_facts(lessons) if lessons else []
    progress(25)
    general = [f for f in facts if not f["personal"]]
    for k, f in enumerate(general):
        f["evidence"] = evidence(f["fact"])
        progress(25 + int(45 * (k + 1) / max(1, len(general))))
    if general:
        judge(general)
    progress(92)
    learned, left_out = [], []
    for f in facts:
        if f["personal"]:
            memory.remember(f["fact"], "treinamento", source="training")
            f.update(verdict="personal", note="")
            learned.append(f)
        elif f["verdict"] == "agree":
            knowledge.learn(_title(f["fact"]), f["fact"] + (f"\n\nFonte: {f['evidence']['source']}" if f["evidence"]["source"] else ""),
                            "Aprendizados")
            learned.append(f)
        else:
            left_out.append(f)
    # agreement with the sources counts only what could be compared (confirmed + contradicted)
    checked = [f for f in general if f["verdict"] in ("agree", "disagree")]
    score = round(100 * sum(f["verdict"] == "agree" for f in checked) / len(checked)) if checked else None
    clean = [{k: v for k, v in f.items() if k != "evidence"} | {"source": (f.get("evidence") or {}).get("source", "")}
             for f in facts]
    db.execute("UPDATE trainings SET finished = ?, score = ?, facts = ? WHERE id = ?",
               (datetime.now().isoformat(timespec="seconds"), score, json.dumps(clean, ensure_ascii=False), sid))
    db.log_action("treinamento", f"Concluiu um treinamento: {len(learned)} aprendido(s), {len(left_out)} deixado(s) de fora")
    progress(100)
    return {"ok": True, "id": sid, "topic": topic, "score": score, "learned": [_public(f) for f in learned],
            "left_out": [_public(f) for f in left_out], "lessons": len(lessons),
            "unchecked": sum(f.get("verdict") == "unknown" for f in general),
            "online": netprobe.effective() != "offline"}


def _public(f: dict) -> dict:
    return {"fact": f["fact"], "verdict": f.get("verdict", ""), "note": f.get("note", ""),
            "source": (f.get("evidence") or {}).get("source", "") or f.get("source", "")}


def history(limit: int = 50) -> list[dict]:
    rows = db.all("SELECT id, topic, started, finished, score, facts FROM trainings WHERE finished IS NOT NULL "
                  "ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["facts"] = json.loads(r["facts"] or "[]")
    return rows


def delete(tid: int):
    db.execute("DELETE FROM trainings WHERE id = ?", (int(tid),))


def summary_text(result: dict) -> str:
    """What NEXUS says at the end ("Análise completa...")."""
    if not result.get("ok"):
        return i18n.t("training_nothing")
    if result["score"] is None:
        if result.get("unchecked"):
            return i18n.t("training_done_unchecked", learned=len(result["learned"]), n=result["unchecked"])
        return i18n.t("training_done_personal", learned=len(result["learned"]))
    return i18n.t("training_done", learned=len(result["learned"]), left=len(result["left_out"]), score=result["score"])

