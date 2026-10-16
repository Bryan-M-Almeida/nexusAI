"""Import memories from other AIs (beta, v0.17.5).

NEXUS shows a ready-made prompt for the chosen AI (ChatGPT, Claude, Gemini, Copilot or another one); the user pastes
it there, copies the answer back and NEXUS keeps each line as a memory tagged with its source ("import:chatgpt").
Parsing is deterministic (one memory per "- [category] text" line), so nothing is invented and no model call is needed;
memories NEXUS already knows (same meaning, other words) are skipped by memory.remember."""
import re

from . import memory
from .db import db

SOURCES = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini", "copilot": "Copilot", "other": "IA"}
CATEGORIES = {"perfil", "preferencia", "rotina", "trabalho", "saude", "pessoas", "objetivos", "outros",
              "profile", "preference", "routine", "work", "health", "people", "goals", "other",
              "preferencia", "salud", "personas", "objetivos", "otros"}

PROMPTS = {
    "pt": ("Liste tudo o que você sabe e lembra sobre mim (memórias, preferências, rotina, trabalho, pessoas, objetivos, "
           "saúde e qualquer outro detalhe que eu já tenha contado). Regras: uma informação por linha, começando com "
           "\"- \" e a categoria entre colchetes, assim: - [preferencia] Gosto de café sem açúcar. Categorias: perfil, "
           "preferencia, rotina, trabalho, saude, pessoas, objetivos, outros. Escreva frases curtas e completas, em "
           "português. Não invente nada; se não souber nada sobre mim, responda apenas NENHUMA."),
    "en": ("List everything you know and remember about me (memories, preferences, routine, work, people, goals, health "
           "and any other detail I have told you). Rules: one item per line, starting with \"- \" and the category in "
           "brackets, like this: - [preference] I like my coffee without sugar. Categories: profile, preference, routine, "
           "work, health, people, goals, other. Write short, complete sentences in English. Don't make anything up; if "
           "you know nothing about me, reply only NONE."),
    "es": ("Enumera todo lo que sabes y recuerdas de mí (recuerdos, preferencias, rutina, trabajo, personas, objetivos, "
           "salud y cualquier otro detalle que te haya contado). Reglas: un dato por línea, empezando con \"- \" y la "
           "categoría entre corchetes, así: - [preferencia] Me gusta el café sin azúcar. Categorías: perfil, "
           "preferencia, rutina, trabajo, salud, personas, objetivos, otros. Frases cortas y completas, en español. No "
           "inventes nada; si no sabes nada de mí, responde solo NINGUNA."),
}
EMPTY = re.compile(r"^\W*(nenhuma|none|ninguna|nada|nothing)\W*$", re.I)
LINE = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+(?:\[([^\]]{1,24})\]\s*)?(.+?)\s*$")


def prompt(lang: str = "pt") -> str:
    return PROMPTS.get(lang, PROMPTS["pt"])


def parse(text: str) -> list[tuple[str, str]]:
    """[(category, memory)] from the other AI's answer. Lines that aren't list items are ignored."""
    items = []
    for raw in (text or "").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        cat = (m.group(1) or "outros").strip().lower()
        cat = re.sub(r"[^a-z]", "", cat.replace("ç", "c").replace("ã", "a").replace("é", "e").replace("ú", "u").replace("á", "a"))
        content = re.sub(r"\*\*|__", "", m.group(2)).strip()
        if len(content) < 6 or EMPTY.match(content):
            continue
        items.append((cat if cat in CATEGORIES else "outros", content[:400]))
    return items


def import_text(source: str, text: str) -> dict:
    source = source if source in SOURCES else "other"
    if EMPTY.match((text or "").strip()):
        return {"ok": True, "added": 0, "skipped": 0, "items": []}
    added, skipped = [], 0
    for cat, content in parse(text):
        saved = memory.remember(content, cat, source=f"import:{source}")
        if saved:
            added.append(content)
        else:
            skipped += 1
    if added:
        db.log_action("memória", f"Importou {len(added)} memória(s) de {SOURCES[source]}")
    return {"ok": True, "added": len(added), "skipped": skipped, "items": added, "source": source}


def by_source() -> list[dict]:
    """How many memories came from each place (NEXUS itself = chat/training)."""
    rows = db.all("SELECT source, COUNT(*) n FROM memories GROUP BY source")
    out: dict = {}
    for r in rows:
        key = r["source"][7:] if r["source"].startswith("import:") else "nexus"
        out[key] = out.get(key, 0) + r["n"]
    return [{"source": k, "name": SOURCES.get(k, "NEXUS" if k == "nexus" else k), "count": v} for k, v in out.items()]
