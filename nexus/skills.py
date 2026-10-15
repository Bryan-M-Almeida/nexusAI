"""Skills (v0.13): NEXUS levels up in each area as it is used. Minimal by design: XP comes from what actually
happened in a turn (tools that ran, the topic of the message, voice, workspace, study mode) - no extra AI calls,
so it costs nothing in performance. Levels follow a gentle curve and map to ranks E -> S."""
import re
import unicodedata

from .db import db, now

# id -> (keywords in pt/en/es matched against the user's message, without accents)
SKILLS = {
    "organization": r"\b(agenda|lembr\w*|remind\w*|recuerd\w*|tarefa\w*|tasks?|tareas?|reuni\w*|meeting|cita|compromiss\w*|prazo|deadline)\b",
    "finance": r"\b(gast\w*|dinheiro|money|dinero|financ\w*|invest\w*|orcamento|budget|presupuesto|salario|salary|cambio|dolar\w*|euro\w*|reais|juros|interest rate)\b",
    "programming": r"\b(codigo|code|program\w*|python|javascript|js|java|html|css|sql|api|bug|funcao|function|funcion|variavel|variable|git|react|node)\b",
    "study": r"\b(estud\w*|study|aprend\w*|learn\w*|prova|exam\w*|simulad\w*|quiz|resum\w*|aula|lesson|clase|explica\w*)\b",
    "health": r"\b(saude|health|salud|exercicio|exercise|treino|workout|dieta|diet|sono|sleep|sueno|remedio|medic\w*|socorr\w*|first aid|auxilio\w*|rcp|cpr)\b",
    "knowledge": r"\b(o que e|what is|que es|quem foi|who was|quien fue|filosof\w*|philosoph\w*|historia|history|ciencia|science|anatom\w*)\b",
    "research": r"\b(noticia\w*|news|clima|weather|tempo hoje|previsao|forecast|wikipedia|pesquis\w*|search|busca\w*)\b",
}
TOOL_SKILL = {  # a tool that ran -> skill credited (actions are worth more than talk)
    "add_task": "organization", "complete_task": "organization", "add_event": "organization",
    "set_reminder": "organization", "list_events": "organization", "list_tasks": "organization",
    "sync_calendar": "organization", "record_data": "finance", "query_data": "finance",
    "convert_currency": "finance", "learn_knowledge": "knowledge", "search_knowledge": "knowledge",
    "wikipedia": "research", "get_news": "research", "get_weather": "research", "emergency": "health",
    "write_file": "programming", "edit_file": "programming", "run_command": "programming", "read_file": "programming",
}
XP_TOPIC, XP_TOOL, XP_VOICE = 4, 10, 3
RANKS = [(0, "E"), (3, "D"), (6, "C"), (10, "B"), (15, "A"), (21, "S")]
_COMPILED = {k: re.compile(v) for k, v in SKILLS.items()}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def xp_for(level: int) -> int:
    """Total XP needed to reach `level` (1 -> 0, 2 -> 60, 3 -> 180, 4 -> 360 ...): 30 * n * (n - 1)."""
    return 30 * level * (level - 1)


def level_of(xp: int) -> int:
    level = 1
    while xp >= xp_for(level + 1):
        level += 1
    return level


def rank_of(level: int) -> str:
    return [r for lv, r in RANKS if level >= lv][-1]


def award(user_text: str, tools_used, spoken: bool = False, workspace: bool = False, study: bool = False) -> list[dict]:
    """Credit XP for one finished turn. Returns the level-ups that happened (for a toast)."""
    gains: dict[str, int] = {}
    text = _norm(user_text or "")
    for skill, rx in _COMPILED.items():
        if rx.search(text):
            gains[skill] = gains.get(skill, 0) + XP_TOPIC
    for name in set(tools_used or ()):
        skill = TOOL_SKILL.get(name)
        if skill:
            gains[skill] = gains.get(skill, 0) + XP_TOOL
    if workspace:
        gains["programming"] = gains.get("programming", 0) + XP_TOPIC
    if study:
        gains["study"] = gains.get("study", 0) + XP_TOPIC
    if spoken:
        gains["voice"] = gains.get("voice", 0) + XP_VOICE
    ups = []
    for skill, xp in gains.items():
        row = db.one("SELECT xp FROM skills WHERE skill = ?", (skill,))
        before = row["xp"] if row else 0
        after = before + xp
        db.execute("INSERT INTO skills(skill, xp, updated) VALUES (?,?,?) ON CONFLICT(skill) DO UPDATE SET "
                   "xp = excluded.xp, updated = excluded.updated", (skill, after, now()))
        if level_of(after) > level_of(before):
            ups.append({"skill": skill, "level": level_of(after), "rank": rank_of(level_of(after))})
    total_before = sum(r["xp"] for r in db.all("SELECT xp FROM skills")) - sum(gains.values())
    total_after = total_before + sum(gains.values())
    if gains and overall_level(total_after) > overall_level(total_before):
        ups.append({"skill": "nexus", "level": overall_level(total_after), "rank": rank_of(overall_level(total_after))})
    return ups


def overall_level(total_xp: int) -> int:
    """NEXUS's own level grows with the sum of all skills, more slowly."""
    return level_of(total_xp // 3)


def summary() -> dict:
    rows = {r["skill"]: r["xp"] for r in db.all("SELECT skill, xp FROM skills")}
    items = []
    for skill in list(SKILLS) + ["voice"]:
        xp = rows.get(skill, 0)
        lv = level_of(xp)
        lo, hi = xp_for(lv), xp_for(lv + 1)
        items.append({"skill": skill, "xp": xp, "level": lv, "rank": rank_of(lv),
                      "progress": round((xp - lo) / (hi - lo), 3), "next": hi - xp})
    total = sum(rows.values())
    lv = overall_level(total)
    return {"skills": items, "level": lv, "rank": rank_of(lv), "total_xp": total,
            "progress": round((total // 3 - xp_for(lv)) / (xp_for(lv + 1) - xp_for(lv)), 3)}
