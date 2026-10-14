"""Conversation control by voice/text: repeat, repeat more clearly, pause, resume, stop.

Short commands are recognised locally (instant, no LLM). Anything longer goes to the model, which can
still decide with the `conversation_control` tool."""
import re
import unicodedata

ACTIONS = ("repeat", "clearer", "pause", "resume", "stop")
MAX_WORDS = 7  # longer utterances are real requests, not control commands


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]+", " ", text).strip()


# Order matters: "clearer" before "repeat" ("nao entendi, repete" = explain better).
PATTERNS = [
    ("clearer", r"\b(nao entendi|n entendi|nao compreendi|explica melhor|explique melhor|mais claro|mais devagar|"
                r"de forma mais clara|i didn t understand|i don t understand|didn t get (it|that)|explain (it )?better|"
                r"more clearly|say it (more )?simpl|slower|no entendi|no lo entendi|explica mejor|mas claro|mas despacio)\b"),
    ("repeat", r"\b(repete|repita|repetir|fala de novo|diz de novo|fala novamente|o que voce disse|"
               r"repeat|say (it|that) again|come again|what did you say|"
               r"repite|repitelo|dilo otra vez|otra vez|que dijiste)\b"),
    ("pause", r"\b(pausa|pause|pausar|espera|espere|aguarda|aguarde|um momento|segura|"
              r"wait|hold on|hold up|one moment|un momento|para un momento)\b"),
    ("resume", r"\b(continua|continue|continuar|prossiga|prosseguir|pode continuar|segue|siga|"
               r"go on|keep going|carry on|resume|continua|sigue|prosigue|puedes seguir)\b"),
    ("stop", r"\b(para|pare|parar|chega|cala|silencio|cancela|interrompe|"
             r"stop|enough|be quiet|shut up|cancel|basta|callate|detente|alto)\b"),
]
_COMPILED = [(a, re.compile(p)) for a, p in PATTERNS]

# Utterances that START like this are pause/stop requests even when long
# ("segura aí que vou atender a porta", "hold on, someone is calling me").
LEADING = [
    ("pause", re.compile(r"^(espera ai|espere ai|peraí|perai|pera ai|pera|segura ai|segura|aguenta ai|hold on|"
                         r"wait a (second|minute|moment)|espera un momento|espera)\b")),
    # "um momento" alone or "um momento que/por favor/aí ..." - not "um momento histórico..."
    ("pause", re.compile(r"^(so )?(um|un|one) (momento|minuto|segundo|moment|minute|second|sec)( (que|por|ai|please|while)\b.*)?$")),
    ("stop", re.compile(r"^(para de falar|pare de falar|chega|cala a boca|fica quieto|silencio|"
                        r"stop talking|stop|shut up|be quiet|that s enough|"
                        r"deja de hablar|callate|basta|silencio)\b")),
]
MAX_LEADING_WORDS = 16


def detect(text: str) -> str | None:
    """Return a control action for short commands like "pausa", "repeat that", "no entendí"; else None."""
    norm = _norm(text)
    words = [w for w in norm.split() if w not in ("nexus", "por", "favor", "please", "ok", "okay", "ei", "hey")]
    if not words:
        return None
    joined = " ".join(words)
    is_question = text.strip().endswith("?")
    if not is_question and len(words) <= MAX_LEADING_WORDS:
        for action, rx in LEADING:
            if rx.search(joined):
                return action
    if len(words) > MAX_WORDS:
        return None
    for action, rx in _COMPILED:
        if not rx.search(joined):
            continue
        # "para"/"continue"/"espera" are also ordinary words ("para quem é...?", "continue a lista..."):
        # treat them as commands only in very short, non-question utterances.
        if action in ("pause", "resume", "stop") and (is_question or len(words) > 3):
            continue
        return action
    return None
