"""NEXUS changes its own settings when asked (v0.18.5): "muda o aro para vermelho", "tema AMD", "voz feminina",
"fala mais rápido", "aro maior", "desliga as animações", "desfaz".

Common requests are recognised without the model (instant); anything else reaches the model, which calls the
`set_preference` tool. Only the settings listed in PREFS can be changed this way, each one validated; the previous
values are kept so "desfaz" / "undo" brings them back. The interface applies the change at once (event "prefs")."""
import re
import unicodedata

from .config import settings

THEMES = {  # ring, core, background
    "nexus": ("#cfe4ff", "#2f86ff", "#0b1f5c"),
    "amd": ("#ffd6d3", "#ed1c24", "#2a0507"),
    "emerald": ("#d5ffea", "#16c47a", "#05271b"),
    "violet": ("#ebdcff", "#8b5cf6", "#1a0b3b"),
    "amber": ("#ffe9c4", "#f59e0b", "#2a1904"),
    "graphite": ("#e6e8ec", "#9aa3b2", "#101318"),
    "ice": ("#e8fbff", "#38bdf8", "#04233a"),
}
THEME_WORDS = [("amd", r"amd|radeon|vermelh[oa] amd|red amd"), ("nexus", r"nexus|original|padrao|default|azul nexus"),
               ("emerald", r"esmeralda|emerald"), ("violet", r"violeta|violet|roxo|purple|morado"),
               ("amber", r"ambar|amber"), ("graphite", r"grafite|graphite|grafito|cinza|gray|grey|gris"),
               ("ice", r"gelo|ice|hielo")]
COLORS = [  # (regex after _norm, hex) - the more specific first
    (r"azul escuro|dark blue|azul oscuro|azul marinho|navy", "#0b1f5c"),
    (r"azul claro|light blue|celeste|azul celeste", "#7cc4ff"),
    (r"verde claro|light green|verde limao|lime", "#84f0a0"),
    (r"vermelh[oa]|red|rojo|roja|carmesim|scarlet", "#ff3030"),
    (r"azul|blue", "#2f86ff"),
    (r"verde|green", "#22c55e"),
    (r"roxo|roxa|purpura|purple|morado|morada|violeta|violet|lilas", "#8b5cf6"),
    (r"rosa|pink", "#ec4899"),
    (r"laranja|orange|naranja", "#f97316"),
    (r"amarel[oa]|yellow|amarill[oa]", "#facc15"),
    (r"dourad[oa]|gold|golden|dorad[oa]", "#d4a72c"),
    (r"branc[oa]|white|blanc[oa]", "#f5f7fa"),
    (r"pret[oa]|black|negr[oa]", "#05060a"),
    (r"ciano|cyan|cian|turquesa|turquoise", "#22d3ee"),
    (r"prata|prateado|silver|plata|plateado", "#c9d2de"),
    (r"cinza|gray|grey|gris", "#6b7280"),
    (r"marrom|brown|marron|cafe", "#8b5a2b"),
]
PARTS = [("color_ring", r"aro|anel|ring|anillo|circulo|circle"), ("color_core", r"nucleo|centro|core|bolinha|miolo"),
         ("color_bg", r"fundo|tela|background|fondo|pantalla|screen")]

PREFS = {  # name: (kind, allowed) - what NEXUS may change by itself
    "theme": ("choice", tuple(THEMES)),
    "color_ring": ("color", None), "color_core": ("color", None), "color_bg": ("color", None),
    "ring_scale": ("int", (60, 140)), "ring_speed": ("choice", ("slow", "normal", "fast")),
    "exchange_size": ("int", (12, 24)), "bg_style": ("choice", ("glow", "solid", "grid")),
    "font_brand": ("choice", ("orbitron", "clean")),
    "cursor_style": ("choice", ("system", "ring", "dot", "arrow")), "cursor_size": ("choice", ("small", "medium", "large")),
    "voice_gender": ("choice", ("male", "female")), "voice_effect": ("choice", ("jarvis", "robot", "none")),
    "tts_speed": ("int", (-5, 10)), "tts_volume": ("int", (0, 100)),
    "show_hud": ("bool", None), "reduce_motion": ("bool", None), "ring_wander": ("bool", None),
    "show_exchange": ("bool", None), "show_captions": ("bool", None), "speak_menus": ("bool", None),
    "require_wake_word": ("bool", None), "ai_mode": ("choice", ("assistant", "direct")),
}
_undo: list[dict] = []


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9#% ]+", " ", text)
    text = re.sub(r"^\s*(ok |ei |hey |oi )?nexus\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def validate(name: str, value):
    """The value to store, or raise ValueError."""
    if name not in PREFS:
        raise ValueError(f"'{name}' can't be changed this way; allowed: {', '.join(PREFS)}")
    kind, allowed = PREFS[name]
    if kind == "color":
        v = str(value).strip().lower()
        if not re.fullmatch(r"#[0-9a-f]{6}", v):
            named = next((h for rx, h in COLORS if re.fullmatch(rf"(?:{rx})", _norm(v))), None)
            if not named:
                raise ValueError("colour must be #rrggbb or a colour name")
            v = named
        return v
    if kind == "choice":
        v = str(value).strip().lower()
        if v not in allowed:
            raise ValueError(f"'{name}' must be one of {allowed}")
        return v
    if kind == "int":
        lo, hi = allowed
        return max(lo, min(hi, int(float(value))))
    if kind == "bool":
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "on", "sim", "yes", "si")
    raise ValueError(name)


def apply(changes: dict) -> dict:
    """Validate and save; the previous values go to the undo stack. A theme sets the three colours."""
    clean = {}
    for name, value in changes.items():
        v = validate(name, value)
        if name == "theme":
            clean.update(zip(("color_ring", "color_core", "color_bg"), THEMES[v]))
        clean[name] = v
    if not clean:
        return {}
    _undo.append({k: settings.get(k) for k in clean})
    del _undo[:-10]
    settings.apply(clean)
    return clean


def undo() -> dict:
    if not _undo:
        return {}
    previous = _undo.pop()
    settings.apply(previous)
    return previous


# ---------------------------------------------------------------- phrases (instant)
CHANGE = (r"(mud[ae]|muda|mudar|troc[ae]|trocar|coloc[ae]|colocar|poe|bota|botar|deix[ae]|deixar|pint[ae]|pintar|"
          r"faz|faca|fazer|us[ae]|usar|ativa|ativar|liga|ligar|set|make|change|turn|use|switch|paint|pon|poner|cambia|"
          r"cambiar|usa|activa|haz|quero|quiero|i want)")
UNDO_RX = re.compile(r"^(desfaz|desfazer|desfaca|volta (como|ao que) estava|volta a cor|undo|undo that|revert|deshaz|deshacer|"
                     r"vuelve como estaba)( isso| that| eso| a mudanca| the change)?$")


def _color_in(fragment: str) -> str | None:
    return next((h for rx, h in COLORS if re.search(rf"\b(?:{rx})\b", fragment)), None)


def detect(text: str) -> dict | None:
    """{"changes": {...}} | {"undo": True} for a clear request to change NEXUS's look or voice; else None."""
    n = _norm(text)
    if not n or len(n.split()) > 16 or text.strip().endswith("?"):
        return None
    if UNDO_RX.match(n):
        return {"undo": True}
    changes = {}
    m = re.search(r"\b(tema|theme|estilo|cores d[ao]|colors of|colores de)\s+(d[ao]\s+|the\s+|el\s+|la\s+)?(\w+)", n)
    if m and re.search(rf"\b{CHANGE}\b|^(tema|theme)\b", n):
        theme = next((t for t, rx in THEME_WORDS if re.fullmatch(rf"(?:{rx})", m.group(3))), None)
        if theme:
            changes["theme"] = theme
    if not changes:
        for name, part in PARTS:  # "aro vermelho", "muda o fundo para preto", "make the ring red"
            pm = re.search(rf"\b({part})\b", n)
            if not pm:
                continue
            after = n[pm.end():pm.end() + 40]
            before = n[max(0, pm.start() - 25):pm.start()]
            color = _color_in(after) or (_color_in(before) if re.search(r"\b(make|paint|turn)\b", n) else None)
            if color:
                changes[name] = color
        if changes and not re.search(rf"\b{CHANGE}\b", n) and len(n.split()) > 5:
            changes = {}  # "o aro vermelho estava lindo ontem" is not a request
    if not changes:
        if re.search(r"\b(voz|voice)\s+(feminina|de mulher|female|femenina|woman)\b|\b(female|feminine) voice\b", n):
            changes["voice_gender"] = "female"
        elif re.search(r"\b(voz|voice)\s+(masculina|de homem|male|masculino|man)\b|\b(male|masculine) voice\b", n):
            changes["voice_gender"] = "male"
        elif re.search(r"\b(fal[ae]|speak|talk|habla)\s+(mais |more |mas )?(rapido|depressa|faster|quicker|rapido)\b", n):
            changes["tts_speed"] = int(settings.get("tts_speed", 0)) + 2
        elif re.search(r"\b(fal[ae]|speak|talk|habla)\s+(mais |more |mas )?(devagar|lento|slower|despacio)\b", n):
            changes["tts_speed"] = int(settings.get("tts_speed", 0)) - 2
        elif re.search(r"\b(aro|ring|anillo)\s+(maior|bigger|larger|mas grande)\b|\b(aumenta|bigger|agranda)\s+(o |the |el )?(aro|ring|anillo)\b", n):
            changes["ring_scale"] = int(settings.get("ring_scale", 100)) + 15
        elif re.search(r"\b(aro|ring|anillo)\s+(menor|smaller|mas pequeno)\b|\b(diminui|shrink|achica)\s+(o |the |el )?(aro|ring|anillo)\b", n):
            changes["ring_scale"] = int(settings.get("ring_scale", 100)) - 15
        elif re.search(r"\b(letra|texto|fonte|text|font|letras)\s+(maior|bigger|larger|mas grande)\b", n):
            changes["exchange_size"] = int(settings.get("exchange_size", 14)) + 2
        elif re.search(r"\b(letra|texto|fonte|text|font|letras)\s+(menor|smaller|mas pequena|mas pequeno)\b", n):
            changes["exchange_size"] = int(settings.get("exchange_size", 14)) - 2
        elif re.search(r"\b(desliga|tira|para|remove|turn off|stop|quita|apaga)\s+(as |the |las )?(animacoes|animations|animaciones)\b", n):
            changes["reduce_motion"] = True
        elif re.search(r"\b(liga|ativa|volta|turn on|enable|activa|pon)\s+(as |the |las )?(animacoes|animations|animaciones)\b", n):
            changes["reduce_motion"] = False
    return {"changes": changes} if changes else None


THEME_NAMES = {"pt": {"nexus": "NEXUS", "amd": "AMD", "emerald": "esmeralda", "violet": "violeta", "amber": "âmbar",
                      "graphite": "grafite", "ice": "gelo"},
               "en": {"nexus": "NEXUS", "amd": "AMD", "emerald": "emerald", "violet": "violet", "amber": "amber",
                      "graphite": "graphite", "ice": "ice"},
               "es": {"nexus": "NEXUS", "amd": "AMD", "emerald": "esmeralda", "violet": "violeta", "amber": "ámbar",
                      "graphite": "grafito", "ice": "hielo"}}
TEXTS = {
    "pt": {"theme": "Pronto: tema {v}.", "color_ring": "Pronto: aro na nova cor.", "color_core": "Pronto: núcleo na nova cor.",
           "color_bg": "Pronto: fundo na nova cor.", "colors": "Pronto: cores trocadas.", "voice_gender": "Pronto, voz trocada.",
           "tts_speed": "Pronto, velocidade da fala ajustada.", "ring_scale": "Pronto: aro em {v}%.",
           "exchange_size": "Pronto: texto em {v} pixels.", "reduce_motion": "Pronto: animações {v}.",
           "on": "desligadas", "off": "ligadas", "undo": "Desfeito: voltei como estava.", "nothing": "Não há nada para desfazer.",
           "generic": "Pronto."},
    "en": {"theme": "Done: {v} theme.", "color_ring": "Done: new ring colour.", "color_core": "Done: new core colour.",
           "color_bg": "Done: new background colour.", "colors": "Done: colours changed.", "voice_gender": "Done, voice changed.",
           "tts_speed": "Done, speech speed adjusted.", "ring_scale": "Done: ring at {v}%.",
           "exchange_size": "Done: text at {v} pixels.", "reduce_motion": "Done: animations {v}.",
           "on": "off", "off": "on", "undo": "Undone: back as it was.", "nothing": "There's nothing to undo.", "generic": "Done."},
    "es": {"theme": "Listo: tema {v}.", "color_ring": "Listo: anillo con el nuevo color.", "color_core": "Listo: núcleo con el nuevo color.",
           "color_bg": "Listo: fondo con el nuevo color.", "colors": "Listo: colores cambiados.", "voice_gender": "Listo, voz cambiada.",
           "tts_speed": "Listo, velocidad del habla ajustada.", "ring_scale": "Listo: anillo al {v}%.",
           "exchange_size": "Listo: texto a {v} píxeles.", "reduce_motion": "Listo: animaciones {v}.",
           "on": "desactivadas", "off": "activadas", "undo": "Deshecho: volví como estaba.", "nothing": "No hay nada que deshacer.",
           "generic": "Listo."},
}


def reply(changes: dict, code: str) -> str:
    T = TEXTS.get(code, TEXTS["pt"])
    keys = [k for k in changes if k != "theme"]
    if "theme" in changes:
        return T["theme"].format(v=THEME_NAMES[code if code in THEME_NAMES else "pt"][changes["theme"]])
    if len(keys) > 1:
        return T["colors"] if all(k.startswith("color_") for k in keys) else T["generic"]
    k = keys[0]
    if k == "reduce_motion":
        return T[k].format(v=T["on" if changes[k] else "off"])
    return T.get(k, T["generic"]).format(v=changes[k])


def handle(text: str, code: str) -> tuple[dict, str] | None:
    """Instant path: (applied changes, reply) or None."""
    cmd = detect(text)
    if not cmd:
        return None
    T = TEXTS.get(code, TEXTS["pt"])
    if cmd.get("undo"):
        previous = undo()
        return (previous, T["undo"]) if previous else ({}, T["nothing"])
    applied = apply(cmd["changes"])
    return applied, reply(cmd["changes"] if "theme" in cmd["changes"] else applied, code)


def set_preference(name: str, value) -> dict:
    """Tool for the model."""
    try:
        applied = apply({name: value})
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    from . import tools

    if tools.prefs_hook:
        tools.prefs_hook(applied)
    return {"ok": True, "applied": applied}
