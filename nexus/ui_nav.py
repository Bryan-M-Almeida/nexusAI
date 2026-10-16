"""The AI opens the interface for the user (v0.16.5): "abre as configurações", "open the panel", "fecha isso".
Short requests that only name a part of NEXUS are recognised here, without the model (instant); anything longer
or vaguer ("quero mudar a cor do aro") reaches the model, which calls the `open_interface` tool. Either way the
interface receives a "ui_open" event: the menu opens and the ring shrinks and waits above it."""
import re
import unicodedata

# target -> words (accents removed, lower case). Order matters: the first match wins.
TARGETS = [
    ("tutorial", r"tutorial"),
    ("guide", r"guia|guide|guia de atalhos|lista de atalhos"),
    ("panel", r"painel|panel|dashboard|agenda|tarefas|tasks|tareas|memorias?|memory|memories"),
    ("conversations", r"conversas|conversations|conversaciones|historico|history|historial"),
    ("notifications", r"notificac\w*|notifications?|notificaciones|avisos|alertas?|alerts?"),
    ("library", r"biblioteca|library|livros|books|libros"),
    ("workspace", r"area de trabalho|workspace|area de trabajo|projetos|projects|proyectos"),
    ("skills", r"habilidades|skills|niveis|levels|niveles"),
    ("settings", r"configurac\w*|configuracion\w*|ajustes|settings|preferencias|preferences|opcoes|options|opciones"),
]
# settings section -> words (only used together with a "settings" word, or alone for the very specific ones)
SECTIONS = [
    ("keys", r"atalhos|shortcuts|atajos|teclas|keys"),
    ("voice", r"voz|voice"),
    ("mic", r"microfone|microphone|microfono|mic"),
    ("perf", r"desempenho|performance|rendimiento|conexao|connection|conexion"),
    ("notif", r"notificac\w*|notifications?|notificaciones"),
    ("integ", r"integrac\w*|integrations?|integraciones"),
    ("ui", r"interface|interfaz|aparencia|appearance|apariencia|cores|colors|colours|colores|cursor|mouse|menus?"),
    ("data", r"dados|data|datos|backup"),
    ("beta", r"beta|modo desenvolvedor|developer mode|modo desarrollador"),
    ("ai", r"inteligencia|intelligence|provedor|provider|proveedor|modelo|model|api"),
    ("general", r"geral|general|idioma|language"),
]
OPEN = (r"(abr[aei]r?|abre|abra|mostr[aeo]r?|mostra|me mostra|open|show( me)?|bring up|go to|muestra(me)?|ve a|ir para|"
        r"vai para|entra(r)? (em|no|na)|acessa(r)?|me leva( para| pra| ate| ao| a| onde)?|leva me|take me( to)?|llevame)")
CLOSE = r"(fech[aeo]r?|fecha|close|cierra|cerrar|sai(a|r)? d[aoe]s?|exit|sal de)"
FILLER = r"(o|a|os|as|the|el|la|los|las|my|meu|minha|meus|minhas|mi|mis|um|uma|de|do|da|dos|das|of|para mim|pra mim|por favor|please)"
MAX_WORDS = 8


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z ]+", " ", text)
    text = re.sub(r"^\s*(ok |ei |hey |oi )?nexus\s+", "", text)
    text = re.sub(r"\b(por favor|please|pra mim|para mim|do nexus|of nexus|de nexus)\b", " ", text)  # don't count as words
    return re.sub(r"\s+", " ", text).strip()


def _find(pairs, text):
    for name, words in pairs:
        if re.search(rf"\b({words})\b", text):
            return name
    return None


# "quero mudar a cor do aro", "change the pointer", "personalizar os atalhos": NEXUS's own settings, by subject.
CHANGE = (r"(mud(a|ar|e|o)|troc(a|ar|e|o)|alter(a|ar|e)|personaliz(a|ar|e)|ajust(a|ar|e)|configur(a|ar|e)|"
          r"change|customi[sz]e|set up|edit|cambi(a|ar|e)|modific(a|ar|e))")
SUBJECTS = [
    ("keys", r"atalhos?|shortcuts?|atajos?|teclas de atalho"),
    ("ui", r"(cor|cores|color|colors|colour|colours|colores)\s+(\w+\s+){0,3}(aro|anel|ring|anillo|nucleo|core|fundo|background|"
           r"nexus|tela|screen|pantalla)|aro|anel do nexus|nucleo do nexus|cursor|ponteiro|pointer|puntero|menus?|layout|"
           r"modo de uso|tema|theme|(aro|ring|anillo|nucleo|core|background|fundo)\s+(colou?rs?|color|cor)"),
    ("voice", r"(sua |tua |a |your |tu )?voz( do nexus)?|(your |the )?voice|velocidade da fala|speech speed"),
    ("mic", r"microfone|microphone|microfono"),
    ("general", r"idioma|language"),
]
MAX_CHANGE_WORDS = 14


def detect_change(norm: str) -> dict | None:
    if len(norm.split()) > MAX_CHANGE_WORDS or not re.search(rf"\b{CHANGE}\b", norm):
        return None
    section = _find(SUBJECTS, norm)
    return {"target": "settings", "section": section} if section else None


def detect(text: str) -> dict | None:
    """{"target": ..., "section": ...} for a short "open X" / "close it" request about NEXUS itself; else None."""
    norm = _norm(text)
    if norm and not text.strip().endswith("?") and not re.match(rf"^{OPEN}\b", norm):
        change = detect_change(norm)
        if change:
            return change
    if not norm or len(norm.split()) > MAX_WORDS or text.strip().endswith("?"):
        return None
    if re.match(rf"^{CLOSE}\b", norm):
        rest = re.sub(rf"^{CLOSE}\s*", "", norm)
        if not rest or re.fullmatch(rf"(({FILLER}|isso|this|eso|isto|tudo|todo|everything|menu|aba|tab|janela|window|"
                                    rf"painel|panel|configurac\w*|settings|guia|guide|ventana|pestana)\s*)+", rest):
            return {"target": "close", "section": None}
        return None
    if not re.match(rf"^{OPEN}\b", norm):
        return None
    rest = re.sub(rf"^{OPEN}\s*", "", norm)
    target = _find(TARGETS, rest)
    section = _find(SECTIONS, rest)
    if target == "settings" or (target is None and section in ("keys", "beta")):
        return {"target": "settings", "section": section or "general"}
    if target in ("notifications",) and re.search(r"configurac|settings|ajustes", rest):
        return {"target": "settings", "section": "notif"}
    if target:
        return {"target": target, "section": None}
    return None


def reply(nav: dict) -> tuple[dict, str]:
    """What NEXUS does and says for a recognised request (beta parts that are off stay closed, with an explanation)."""
    from . import features, i18n, tools

    feat = tools.UI_BETA.get(nav["target"])
    if nav["target"] == "close":
        return nav, i18n.t("ui_closing")
    if feat and not features.enabled(feat):
        return {"target": "none", "section": None}, i18n.t("ui_beta_off", name=i18n.t("ui_n_" + nav["target"]).capitalize())
    return nav, i18n.t("ui_opening", name=i18n.t("ui_n_" + nav["target"]))
