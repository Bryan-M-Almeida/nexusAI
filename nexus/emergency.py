"""Emergency mode: first-aid requests are answered instantly and literally from the bundled manual.

Why: on 2026-10-13 a real "preciso fazer RCP, como faço?" was answered by the model with hand placement on the
xiphoid process and "do CPR for 10 to 15 minutes" - both wrong and dangerous - because keyword search did not
retrieve the manual and the model improvised (NX-LLM-021). Here, recognised emergencies never depend on the model:
the first answer is the manual's protocol (plus the emergency number); follow-up questions on the same topic go to
the model with that protocol always in context and a strict "manual only" rule."""
import re
import time
import unicodedata

from .db import db

# topic -> (pattern on normalised text, heading prefix in the pt / en / es first-aid manuals)
TOPICS = {
    "cpr": (r"\b(rcp|reanima\w*|massagem cardiaca|parada (cardiaca|cardiorrespiratoria)|nao (esta )?respira\w*|"
            r"sem pulso|cpr|cardiac arrest|not breathing|isn t breathing|no pulse|resucit\w*|paro cardiaco|"
            r"parada cardiorrespiratoria|no respira)",
            {"pt": "Parada cardiorrespiratória", "en": "Cardiac arrest", "es": "Parada cardiorrespiratoria"}),
    "choking": (r"\b(engasg\w*|sufoc\w*|obstrucao das vias|choking|chok\w*|atragant\w*|se (esta )?ahogando)",
                {"pt": "Engasgo", "en": "Choking", "es": "Atragantamiento"}),
    "bleeding": (r"\b(sangr\w*|hemorrag\w*|bleed\w*|sangrado|sangra\w*)",
                 {"pt": "Sangramentos", "en": "Bleeding", "es": "Hemorragias"}),
    "burn": (r"\b(queim(ei|ou|aram|ando|ad[oa]s?|adura\w*)|se queim\w*|burn(ed|t)|a burn|quem(e|o|ad[oa]s?|adura\w*))\b",
             {"pt": "Queimaduras", "en": "Burns", "es": "Quemaduras"}),
    "fracture": (r"\b(fratur\w*|quebrou o (braco|osso|pe|tornozelo|punho)|osso quebrado|broken (bone|arm|leg)|"
                 r"fractur\w*|hueso roto|se rompio)",
                 {"pt": "Fraturas", "en": "Fractures", "es": "Fracturas"}),
    "seizure": (r"\b(convuls\w*|ataque epilep\w*|crise epilep\w*|seizure\w*|convulsion\w*)",
                {"pt": "Convulsão", "en": "Seizures", "es": "Convulsiones"}),
    "stroke": (r"\b(avc|derrame|stroke|ictus|boca torta|rosto caido|face drooping)",
               {"pt": "AVC", "en": "Stroke", "es": "Ictus"}),
    "heart_attack": (r"\b(infart\w*|ataque cardiaco|dor no peito|heart attack|chest pain|dolor (en el|de) pecho)",
                     {"pt": "Infarto", "en": "Heart attack", "es": "Infarto"}),
    "fainting": (r"\b(desmai\w*|desmay\w*|faint\w*|passed out|perdeu os sentidos)",
                 {"pt": "Desmaio", "en": "Fainting", "es": "Desmayo"}),
    "poisoning": (r"\b(intoxica\w*|envenen\w*|poison\w*|veneno|engoliu (remedio|produto)|swallowed)",
                  {"pt": "Intoxicação", "en": "Poisoning", "es": "Intoxicaciones"}),
    "other": (r"\b(hipoglic\w*|insolacao|choque eletrico|eletrocut\w*|heatstroke|electric shock|hipogluc\w*|"
              r"golpe de calor|descarga electrica)",
              {"pt": "Hipoglicemia", "en": "Low blood sugar", "es": "Hipoglucemia"}),
    # Last: generic "I need to help someone now" -> golden rules (safety, call for help).
    "general": (r"\b(socorr\w*|primeiros socorros|emergencia|acidente|acidentad\w*|help someone|first aid|emergency|"
                r"primeros auxilios|auxilio|accidente)",
                {"pt": "Regras de ouro", "en": "Golden rules", "es": "Reglas de oro"}),
}
_COMPILED = {topic: re.compile(rx) for topic, (rx, _) in TOPICS.items()}

CALL = {
    "pt": "EMERGÊNCIA: ligue agora para o SAMU 192 (ou Bombeiros 193) e coloque no viva-voz.",
    "en": "EMERGENCY: call emergency services now (911 in the US, 112 in Europe) and put the phone on speaker.",
    "es": "EMERGENCIA: llama ya a emergencias (112 en España y la UE, 911 en gran parte de América) y pon el altavoz.",
}
ASK = {
    "pt": "Me diga o que aconteceu: a pessoa responde? Está respirando?",
    "en": "Tell me what happened: does the person respond? Are they breathing?",
    "es": "Dime qué pasó: ¿la persona responde? ¿Respira?",
}
SOURCE = {"pt": "Fonte: Manual de Primeiros Socorros do NEXUS.", "en": "Source: NEXUS First Aid Manual.",
          "es": "Fuente: Manual de Primeros Auxilios de NEXUS."}
REPEAT_AFTER_S = 10 * 60  # the full protocol is given again only after 10 minutes on the same topic


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", text)


# Technical contexts that reuse emergency words ("o código está sangrando memória", "burn CPU cycles").
_TECH = re.compile(r"\b(codigo|code|memoria|memory|ram|cpu|gpu|leak|vazamento|servidor|server|bug|deploy|build|app)\b")


def detect(text: str) -> str | None:
    """Emergency topic or None. Errs on the side of caution: a false alarm only shows a protocol."""
    norm = _norm(text)
    tech = _TECH.search(norm)
    for topic, rx in _COMPILED.items():
        if rx.search(norm) and not (tech and topic in ("bleeding", "burn", "general")):
            return topic
    return None


def section(topic: str, lang: str) -> dict | None:
    """The manual's section for this topic, in the given language (falls back to Portuguese)."""
    for code in (lang, "pt"):
        prefix = TOPICS[topic][1].get(code)
        row = db.one(
            "SELECT c.heading, c.content FROM kb_chunks c JOIN kb_docs d ON d.id = c.doc_id "
            "WHERE d.source LIKE ? AND c.heading LIKE ? LIMIT 1", (f"seed:{code}/%", f"{prefix}%"))
        if row:
            return {**row, "lang": code}
    return None


class Tracker:
    """Remembers which protocols were already given, so follow-ups go to the model instead of repeating."""

    def __init__(self):
        self.given: dict[str, float] = {}

    def first_time(self, topic: str) -> bool:
        return time.time() - self.given.get(topic, 0) > REPEAT_AFTER_S

    def mark(self, topic: str):
        self.given[topic] = time.time()


def protocol_reply(topic: str, lang: str) -> str:
    sec = section(topic, lang)
    lang = sec["lang"] if sec else lang
    parts = [CALL.get(lang, CALL["pt"])]
    if sec:
        parts.append(f"**{sec['heading']}**\n{sec['content']}")
    if topic == "general":
        parts.append(ASK.get(lang, ASK["pt"]))
    parts.append(f"_{SOURCE.get(lang, SOURCE['pt'])}_")
    return "\n\n".join(parts)


RULE = ("MEDICAL EMERGENCY / FIRST AID: answer ONLY with what the manual excerpt below says. Do not add hand "
        "positions, durations, doses or steps that are not in it; if the manual doesn't cover the question, say so and "
        "tell the user to follow the emergency operator's instructions. Keep it short and actionable.")
