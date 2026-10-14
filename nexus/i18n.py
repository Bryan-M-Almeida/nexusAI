"""Portuguese / English / Spanish strings used on the Python side (prompts, reminders, greetings)."""
import re

from .config import settings
from .db import db

STRINGS = {
    "pt": {
        "intro_anon": "Olá, eu sou NEXUS, seu assistente virtual. Para começarmos, importe o seu perfil do formulário NEXUS.",
        "intro": "Olá, {name}. Eu sou NEXUS, seu assistente virtual. Vou aprender sobre você, cuidar da sua agenda, "
                 "tarefas e dados, e responder por voz ou texto. O que teremos para hoje?",
        "hello": "Olá, {name}, o que teremos para hoje?",
        "continue": "Olá, {name}, vamos continuar {topics}?",
        "and": "e",
        "event_soon": "Lembrete: {title} às {time}.",
        "task_due": "Tarefa vencendo: {title}.",
        "llm_offline": "Meu núcleo de IA está offline. Inicie o Ollama e tente novamente.",
        "reply_lang": "Responda em português do Brasil, a menos que o usuário escreva em outro idioma.",
    },
    "en": {
        "intro_anon": "Hello, I am NEXUS, your virtual assistant. To get started, import your profile from the NEXUS form.",
        "intro": "Hello, {name}. I am NEXUS, your virtual assistant. I will learn about you, take care of your schedule, "
                 "tasks and data, and answer by voice or text. What do we have for today?",
        "hello": "Hello, {name}, what do we have for today?",
        "continue": "Hello, {name}, shall we continue {topics}?",
        "and": "and",
        "event_soon": "Reminder: {title} at {time}.",
        "task_due": "Task due: {title}.",
        "llm_offline": "My AI core is offline. Start Ollama and try again.",
        "reply_lang": "Always reply in English unless the user writes in another language.",
    },
    "es": {
        "intro_anon": "Hola, soy NEXUS, tu asistente virtual. Para empezar, importa tu perfil del formulario NEXUS.",
        "intro": "Hola, {name}. Soy NEXUS, tu asistente virtual. Aprenderé sobre ti, me ocuparé de tu agenda, "
                 "tareas y datos, y responderé por voz o texto. ¿Qué tenemos para hoy?",
        "hello": "Hola, {name}, ¿qué tenemos para hoy?",
        "continue": "Hola, {name}, ¿continuamos con {topics}?",
        "and": "y",
        "event_soon": "Recordatorio: {title} a las {time}.",
        "task_due": "Tarea por vencer: {title}.",
        "llm_offline": "Mi núcleo de IA está fuera de línea. Inicia Ollama e inténtalo de nuevo.",
        "reply_lang": "Responde en español, a menos que el usuario escriba en otro idioma.",
    },
}
LANGS = tuple(STRINGS)
WEEKDAYS = {  # Monday first, matching datetime.weekday()
    "pt": ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
}


def lang() -> str:
    """Active language: explicit setting, else the profile language from the landing form."""
    chosen = settings.get("language", "auto")
    if chosen in STRINGS:
        return chosen
    code = str((db.get_profile() or {}).get("language", "pt")).lower()[:2]
    return code if code in STRINGS else "pt"


_MARKERS = {
    "pt": {"você", "voce", "não", "nao", "é", "está", "eu", "meu", "minha", "que", "de", "um", "uma", "para", "com",
           "como", "quanto", "gastei", "amanhã", "hoje", "faço", "isso", "tenho", "lembra", "me", "do", "da"},
    "en": {"the", "you", "what", "is", "are", "do", "does", "my", "i", "how", "about", "to", "and", "of", "it",
           "tomorrow", "today", "remind", "please", "can", "have", "answer"},
    "es": {"qué", "que", "tengo", "mis", "mañana", "hoy", "es", "el", "los", "las", "cómo", "cuánto", "por", "favor",
           "recuérdame", "y", "de", "un", "una", "para", "con", "pendientes", "gasté"},
}


def detect(text: str) -> str | None:
    """Rough language guess for one message (pt/en/es) from common words; None when unsure."""
    words = re.findall(r"[a-záéíóúâêôãõçñ¿¡]+", text.lower())
    if len(words) < 2:
        return None
    scores = {code: sum(w in marks for w in words) for code, marks in _MARKERS.items()}
    if "¿" in text or "¡" in text or "ñ" in text:
        scores["es"] += 2
    if any(c in text for c in "ãõç"):
        scores["pt"] += 2
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    return best if ranked[0] >= 2 and ranked[0] > ranked[1] else None


def t(key: str, **kw) -> str:
    return STRINGS[lang()][key].format(**kw)
