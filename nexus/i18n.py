"""Portuguese / English / Spanish strings used on the Python side (prompts, reminders, greetings)."""
import re

from .config import settings
from .db import db

STRINGS = {
    "pt": {
        "morning": "Bom dia", "afternoon": "Boa tarde", "evening": "Boa noite",
        "greet": "{hello}, {name}. Sistemas online.",
        "agenda_today": "Você tem {n} compromisso(s) hoje: {items}.",
        "agenda_free": "Sua agenda de hoje está livre.",
        "tasks_pending": "{n} tarefa(s) pendente(s), {late} atrasada(s).",
        "event_soon": "Lembrete: {title} às {time}.",
        "task_due": "Tarefa vencendo: {title}.",
        "llm_offline": "Meu núcleo de IA está offline. Inicie o Ollama e tente novamente.",
        "no_profile": "Olá. Ainda não te conheço — importe o seu perfil do formulário NEXUS para começarmos.",
        "reply_lang": "Responda em português do Brasil, a menos que o usuário escreva em outro idioma.",
        "yes": "Sim?",
    },
    "en": {
        "morning": "Good morning", "afternoon": "Good afternoon", "evening": "Good evening",
        "greet": "{hello}, {name}. All systems online.",
        "agenda_today": "You have {n} event(s) today: {items}.",
        "agenda_free": "Your schedule is clear today.",
        "tasks_pending": "{n} pending task(s), {late} overdue.",
        "event_soon": "Reminder: {title} at {time}.",
        "task_due": "Task due: {title}.",
        "llm_offline": "My AI core is offline. Start Ollama and try again.",
        "no_profile": "Hello. I don't know you yet — import your NEXUS form profile so we can begin.",
        "reply_lang": "Always reply in English unless the user writes in another language.",
        "yes": "Yes?",
    },
    "es": {
        "morning": "Buenos días", "afternoon": "Buenas tardes", "evening": "Buenas noches",
        "greet": "{hello}, {name}. Sistemas en línea.",
        "agenda_today": "Tienes {n} compromiso(s) hoy: {items}.",
        "agenda_free": "Tu agenda de hoy está libre.",
        "tasks_pending": "{n} tarea(s) pendiente(s), {late} atrasada(s).",
        "event_soon": "Recordatorio: {title} a las {time}.",
        "task_due": "Tarea por vencer: {title}.",
        "llm_offline": "Mi núcleo de IA está fuera de línea. Inicia Ollama e inténtalo de nuevo.",
        "no_profile": "Hola. Aún no te conozco: importa tu perfil del formulario NEXUS para empezar.",
        "reply_lang": "Responde en español, a menos que el usuario escriba en otro idioma.",
        "yes": "¿Sí?",
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
