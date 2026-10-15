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
        "repeat_button": "Acho que não entendeu, vou repetir.",
        "repeat_intro": "Claro, vou repetir.",
        "clearer_intro": "Tudo bem, vou explicar de outro jeito.",
        "clearer_request": "Eu disse: \"{said}\". Não entendi sua última resposta. Explique o SIGNIFICADO dela com palavras "
                           "simples e frases curtas (se for uma piada, explique o trocadilho e por que é engraçada). "
                           "Não repita a mesma frase.",
        "report_saved": "Pronto, salvei esta conversa para o relatório de erros. Envie o arquivo `{file}` para a equipe.",
        "reminder_now": "Lembrete: {title}, agora.",
        "reminder_in": "Lembrete: {title} em {when}, às {time}.",
        "task_in": "Tarefa vence em {when}, às {time}: {title}.",
        "lead_minutes": "{n} minutos",
        "lead_hour": "1 hora",
        "lead_hours": "{n} horas",
        "lead_day": "1 dia",
        "lead_days": "{n} dias",
        "briefing_title": "Resumo do dia",
        "briefing_hello": "Bom dia, {name}.",
        "briefing_events": "Hoje você tem {n} compromisso(s): {items}.",
        "briefing_no_events": "Sua agenda de hoje está livre.",
        "briefing_tasks": "E {n} tarefa(s) pendente(s).",
        "briefing_no_tasks": "Nenhuma tarefa pendente.",
        "notif_event": "Compromisso",
        "notif_task": "Tarefa",
        "notif_test": "Notificações funcionando. É assim que eu aviso dos seus lembretes.",
        "mode_study": "Estudo",
        "confirm_command": "Posso executar um comando na área de trabalho? Confirme na tela.",
        "already_running": "O NEXUS já está aberto. Procure a janela dele na barra de tarefas.",
        "mode_on": "Executando em modo {mode}.",
        "mode_assistant": "Assistente",
        "mode_direct": "Direto",
        "nothing_to_repeat": "Ainda não falei nada para repetir.",
        "event_soon": "Lembrete: {title} às {time}.",
        "task_due": "Tarefa vencendo: {title}.",
        "llm_offline": "Meu núcleo de IA está offline. Inicie o Ollama e tente novamente.",
        "llm_err_local_down": "Meu núcleo de IA está offline. Inicie o Ollama (ou o LM Studio) e tente novamente.",
        "llm_err_network": "Não consegui falar com o provedor de IA: sem conexão com a internet ou endereço errado.",
        "llm_err_offline_mode": "Estou no modo offline e a IA escolhida fica na internet. Use a IA local ou mude a conexão em Configurações > Desempenho.",
        "llm_err_auth": "O provedor de IA recusou a chave de API (inválida, expirada ou sem permissão). Confira em Configurações > Inteligência.",
        "llm_err_billing": "O provedor de IA recusou por falta de créditos ou pagamento pendente. Verifique sua conta no provedor ou volte para a IA local.",
        "llm_err_rate": "Limite de uso do provedor de IA atingido. Espere um pouco e tente de novo.",
        "llm_err_model": "O modelo \"{model}\" não foi encontrado nesse provedor. Escolha outro em Configurações > Inteligência.",
        "llm_err_server": "O provedor de IA está com problemas agora (erro do servidor). Tente de novo em instantes ou use a IA local.",
        "llm_err_other": "A IA não conseguiu responder. O detalhe ficou registrado no log (Configurações > Dados > Relatar erro).",
        "reply_lang": "Responda em português do Brasil, a menos que o usuário escreva em outro idioma.",
    },
    "en": {
        "intro_anon": "Hello, I am NEXUS, your virtual assistant. To get started, import your profile from the NEXUS form.",
        "intro": "Hello, {name}. I am NEXUS, your virtual assistant. I will learn about you, take care of your schedule, "
                 "tasks and data, and answer by voice or text. What do we have for today?",
        "hello": "Hello, {name}, what do we have for today?",
        "continue": "Hello, {name}, shall we continue {topics}?",
        "and": "and",
        "repeat_button": "I don't think you understood, I'll repeat.",
        "repeat_intro": "Sure, I'll repeat.",
        "clearer_intro": "No problem, let me explain it another way.",
        "clearer_request": "I said: \"{said}\". I didn't understand your last answer. Explain its MEANING in simple words "
                           "and short sentences (if it was a joke, explain the wordplay and why it is funny). "
                           "Don't repeat the same sentence.",
        "report_saved": "Done, I saved this conversation for the error report. Send the file `{file}` to the team.",
        "reminder_now": "Reminder: {title}, now.",
        "reminder_in": "Reminder: {title} in {when}, at {time}.",
        "task_in": "Task due in {when}, at {time}: {title}.",
        "lead_minutes": "{n} minutes",
        "lead_hour": "1 hour",
        "lead_hours": "{n} hours",
        "lead_day": "1 day",
        "lead_days": "{n} days",
        "briefing_title": "Daily briefing",
        "briefing_hello": "Good morning, {name}.",
        "briefing_events": "Today you have {n} appointment(s): {items}.",
        "briefing_no_events": "Your schedule is clear today.",
        "briefing_tasks": "And {n} pending task(s).",
        "briefing_no_tasks": "No pending tasks.",
        "notif_event": "Appointment",
        "notif_task": "Task",
        "notif_test": "Notifications are working. This is how I remind you of things.",
        "mode_study": "Study",
        "confirm_command": "May I run a command in the workspace? Please confirm on screen.",
        "already_running": "NEXUS is already open. Look for its window on the taskbar.",
        "mode_on": "Running in {mode} mode.",
        "mode_assistant": "Assistant",
        "mode_direct": "Direct",
        "nothing_to_repeat": "I haven't said anything to repeat yet.",
        "event_soon": "Reminder: {title} at {time}.",
        "task_due": "Task due: {title}.",
        "llm_offline": "My AI core is offline. Start Ollama and try again.",
        "llm_err_local_down": "My AI core is offline. Start Ollama (or LM Studio) and try again.",
        "llm_err_network": "I couldn't reach the AI provider: no internet connection or a wrong address.",
        "llm_err_offline_mode": "I'm in offline mode and the chosen AI is on the internet. Use the local AI or change the connection in Settings > Performance.",
        "llm_err_auth": "The AI provider rejected the API key (invalid, expired or without permission). Check it in Settings > Intelligence.",
        "llm_err_billing": "The AI provider refused for lack of credits or a pending payment. Check your account with the provider or switch back to the local AI.",
        "llm_err_rate": "The AI provider's usage limit was reached. Wait a little and try again.",
        "llm_err_model": "The model \"{model}\" wasn't found at this provider. Pick another one in Settings > Intelligence.",
        "llm_err_server": "The AI provider is having problems right now (server error). Try again shortly or use the local AI.",
        "llm_err_other": "The AI couldn't answer. The details were saved to the log (Settings > Data > Report an error).",
        "reply_lang": "Always reply in English unless the user writes in another language.",
    },
    "es": {
        "intro_anon": "Hola, soy NEXUS, tu asistente virtual. Para empezar, importa tu perfil del formulario NEXUS.",
        "intro": "Hola, {name}. Soy NEXUS, tu asistente virtual. Aprenderé sobre ti, me ocuparé de tu agenda, "
                 "tareas y datos, y responderé por voz o texto. ¿Qué tenemos para hoy?",
        "hello": "Hola, {name}, ¿qué tenemos para hoy?",
        "continue": "Hola, {name}, ¿continuamos con {topics}?",
        "and": "y",
        "repeat_button": "Creo que no lo entendiste, lo repito.",
        "repeat_intro": "Claro, lo repito.",
        "clearer_intro": "Está bien, te lo explico de otra forma.",
        "clearer_request": "Dije: \"{said}\". No entendí tu última respuesta. Explica su SIGNIFICADO con palabras sencillas "
                           "y frases cortas (si era un chiste, explica el juego de palabras y por qué es gracioso). "
                           "No repitas la misma frase.",
        "report_saved": "Listo, guardé esta conversación para el reporte de errores. Envía el archivo `{file}` al equipo.",
        "reminder_now": "Recordatorio: {title}, ahora.",
        "reminder_in": "Recordatorio: {title} en {when}, a las {time}.",
        "task_in": "La tarea vence en {when}, a las {time}: {title}.",
        "lead_minutes": "{n} minutos",
        "lead_hour": "1 hora",
        "lead_hours": "{n} horas",
        "lead_day": "1 día",
        "lead_days": "{n} días",
        "briefing_title": "Resumen del día",
        "briefing_hello": "Buenos días, {name}.",
        "briefing_events": "Hoy tienes {n} compromiso(s): {items}.",
        "briefing_no_events": "Tu agenda de hoy está libre.",
        "briefing_tasks": "Y {n} tarea(s) pendiente(s).",
        "briefing_no_tasks": "Ninguna tarea pendiente.",
        "notif_event": "Compromiso",
        "notif_task": "Tarea",
        "notif_test": "Las notificaciones funcionan. Así te aviso de tus recordatorios.",
        "mode_study": "Estudio",
        "confirm_command": "¿Puedo ejecutar un comando en el área de trabajo? Confírmalo en pantalla.",
        "already_running": "NEXUS ya está abierto. Busca su ventana en la barra de tareas.",
        "mode_on": "Ejecutando en modo {mode}.",
        "mode_assistant": "Asistente",
        "mode_direct": "Directo",
        "nothing_to_repeat": "Todavía no he dicho nada que repetir.",
        "event_soon": "Recordatorio: {title} a las {time}.",
        "task_due": "Tarea por vencer: {title}.",
        "llm_offline": "Mi núcleo de IA está fuera de línea. Inicia Ollama e inténtalo de nuevo.",
        "llm_err_local_down": "Mi núcleo de IA está fuera de línea. Inicia Ollama (o LM Studio) e inténtalo de nuevo.",
        "llm_err_network": "No pude contactar al proveedor de IA: sin conexión a internet o dirección incorrecta.",
        "llm_err_offline_mode": "Estoy en modo sin conexión y la IA elegida está en internet. Usa la IA local o cambia la conexión en Configuración > Rendimiento.",
        "llm_err_auth": "El proveedor de IA rechazó la clave de API (inválida, caducada o sin permiso). Revísala en Configuración > Inteligencia.",
        "llm_err_billing": "El proveedor de IA lo rechazó por falta de créditos o un pago pendiente. Revisa tu cuenta o vuelve a la IA local.",
        "llm_err_rate": "Se alcanzó el límite de uso del proveedor de IA. Espera un poco y vuelve a intentarlo.",
        "llm_err_model": "El modelo \"{model}\" no existe en este proveedor. Elige otro en Configuración > Inteligencia.",
        "llm_err_server": "El proveedor de IA tiene problemas ahora (error del servidor). Inténtalo en unos instantes o usa la IA local.",
        "llm_err_other": "La IA no pudo responder. El detalle quedó en el registro (Configuración > Datos > Reportar error).",
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
