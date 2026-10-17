"""Scripted tutorial (v0.20.0): a fixed, spoken script - no AI.

While it runs the AI is closed (messages and voice only move the tutorial: next / back / skip) and NEXUS uses the
time to get ready in the background: the model is loaded and its prompt cached, the voice model is loaded (or
downloaded), the app list and the integrations are refreshed. After the tutorial everything answers at full speed."""
import re
import time
import unicodedata

MAX_WORDS = 6  # "próximo, por favor" is a command; a longer sentence is a question the AI answers after the tutorial

PATTERNS = [  # order matters: "voltar ao início" is back, "pular tudo" is skip
    ("skip", r"\b(pula|pular|pule|pulo|skip|salta|saltar|salte|omitir|chega de tutorial|fecha o tutorial|"
             r"encerra o tutorial|termina o tutorial|close the tutorial|end the tutorial|cierra el tutorial)\b"),
    ("back", r"\b(volta|voltar|volte|anterior|repete|repita|de novo|back|previous|go back|again|repeat|"
             r"vuelve|volver|atras|repite|otra vez)\b"),
    ("next", r"\b(proximo|proxima|avanca|avancar|avance|seguinte|continua|continuar|segue|ok|certo|entendi|"
             r"next|continue|go on|got it|okay|siguiente|sigue|seguir|avanza|vale|listo|entiendo)\b"),
]
_COMPILED = [(a, re.compile(p)) for a, p in PATTERNS]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]+", " ", text).strip()


def detect(text: str) -> str | None:
    """'próximo' -> next, 'volta' -> back, 'pula o tutorial' -> skip; anything else -> None."""
    norm = re.sub(r"^(nexus|nexo|next us)\s+", "", _norm(text))
    if not norm or len(norm.split()) > MAX_WORDS:
        return None
    for action, rx in _COMPILED:
        if rx.search(norm):
            return action
    return None


def background(api, emit) -> dict:
    """The jobs that run while the tutorial talks. Each one reports running -> done / skip / error."""
    from . import apps, connectors, legal
    from .config import settings

    results = {}

    def job(name, fn):
        emit("tutorial_bg", {"task": name, "state": "running"})
        t0 = time.time()
        try:
            state = fn() or "done"
        except Exception as exc:  # a background job never breaks the tutorial
            state = "error"
            results[name + "_error"] = f"{type(exc).__name__}: {exc}"[:160]
        results[name] = state
        emit("tutorial_bg", {"task": name, "state": state, "seconds": round(time.time() - t0, 1)})

    def ai():
        if api.ai_state == "cold":
            api._warm_up()
        deadline = time.time() + 180
        while api.ai_state == "warming" and time.time() < deadline:
            time.sleep(0.5)
        return {"ready": "done", "offline": "error"}.get(api.ai_state, "error")

    def voice():
        if not legal.accepted():
            return "skip"
        api._listener.ensure_model()  # first use downloads the Whisper model (shown in Downloads)
        deadline = time.time() + 600
        while api._listener.model_state == "loading" and time.time() < deadline:
            time.sleep(0.5)
        return "done" if api._listener.ready else "error"

    def app_list():
        apps.list_apps(refresh=True)

    def integrations():
        if not connectors.online_allowed():
            return "skip"
        city = settings.get("home_city", "")
        if city and connectors.enabled("weather"):
            for days in (1, 2):  # "como está o tempo" and "vai chover amanhã"
                connectors.call("weather", {"city": city, "days": days})
        if connectors.enabled("currency") and connectors.home_currency() != "USD":
            connectors.call("currency", {"amount": 1.0, "from_currency": "USD", "to_currency": connectors.home_currency()})
        return "done"

    for name, fn in (("ai", ai), ("voice", voice), ("apps", app_list), ("integrations", integrations)):
        job(name, fn)
    emit("tutorial_bg", {"task": "all", "state": "done"})
    return results
