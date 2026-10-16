"""Open the user's apps by name (v0.18.0) and keep games free of NEXUS.

The list comes from the Start menu (Get-StartApps: classic programs, Store apps and Steam shortcuts), refreshed at
most every 10 minutes. Each app is "work" (opened and NEXUS stays), "game" (NEXUS suspends itself: the model leaves
the graphics card, the window minimizes and only "Nexus" by voice or the user going back to the window wakes it) or
"launcher" (Steam, Xbox...: opened without suspending). The user can mark any app either way in Settings > Apps.
With "game watch" on, a game started outside NEXUS is noticed too (only the window in the foreground is checked)."""
import ctypes
import difflib
import json
import os
import re
import subprocess
import threading
import time
import unicodedata
from ctypes import wintypes

from .config import settings

NO_WINDOW = 0x08000000
_lock = threading.Lock()
_apps: list[dict] = []
_loaded = 0.0
REFRESH = 600

GAME_PATH = re.compile(r"steam://rungameid|steamapps|epic games|riot games|xboxgames|gog games|ubisoft game launcher\\games|"
                       r"ea games|battle\.net\\.*\\|emulador|emulator|retroarch|pcsx2|rpcs3|dolphin|yuzu|ryujinx|cemu|"
                       r"duckstation|ppsspp|minecraft|roblox\\versions\\.*robloxplayer", re.I)
GAME_NAME = re.compile(r"\b(minecraft|valorant|league of legends|fortnite|roblox$|gta|grand theft auto|counter[- ]strike|cs2|"
                       r"dota|overwatch|apex legends|call of duty|warzone|elden ring|cyberpunk|the sims|fifa|ea sports fc|"
                       r"rocket league|genshin|honkai|pubg|rainbow six|destiny|diablo|world of warcraft|hearthstone|"
                       r"forza|halo|age of empires|baldur|starfield|palworld|terraria|stardew|hollow knight|among us|"
                       r"retroarch|pcsx2|dolphin|yuzu|ryujinx|rpcs3|cemu|solitaire)\b", re.I)
LAUNCHER = re.compile(r"^(steam|epic games launcher|xbox|battle\.net|ea|ea app|ubisoft connect|gog galaxy|hydra|"
                      r"riot client|rockstar games launcher|playnite|game bar)$", re.I)
NOT_GAME = re.compile(r"wallpaper engine|roblox studio|steam support", re.I)
SKIP = re.compile(r"\.(txt|chm|html?|pdf|url|msc)$|^https?://|uninstall|desinstal|^unins|readme|release notes|"
                  r"documentation|manual|website|faq|help$", re.I)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#. ]+", " ", text)).strip()


def kind(app: dict) -> str:
    name = app["name"]
    if name in settings.get("apps_games", []):
        return "game"
    if name in settings.get("apps_work", []):
        return "work"
    if NOT_GAME.search(name):
        return "work"
    if LAUNCHER.match(name.strip()):
        return "launcher"
    if GAME_PATH.search(app.get("id", "")) or GAME_NAME.search(name):
        return "game"
    return "work"


def _load_start_apps() -> list[dict]:
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                          "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                          "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
                         capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW, encoding="utf-8",
                         errors="replace").stdout.strip()
    rows = json.loads(out) if out else []
    rows = [rows] if isinstance(rows, dict) else rows
    apps, seen = [], set()
    for r in rows:
        name, app_id = (r.get("Name") or "").strip(), (r.get("AppID") or "").strip()
        if not name or not app_id or (SKIP.search(app_id) and not app_id.startswith("steam://")) or SKIP.search(name):
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        apps.append({"name": name, "id": app_id})
    return apps


def list_apps(refresh: bool = False) -> list[dict]:
    global _apps, _loaded
    with _lock:
        if refresh or not _apps or time.time() - _loaded > REFRESH:
            try:
                _apps, _loaded = _load_start_apps(), time.time()
            except (subprocess.SubprocessError, OSError, ValueError):
                pass
        return [{**a, "kind": kind(a)} for a in _apps]


ALIASES = {"vscode": "visual studio code", "vs code": "visual studio code", "code": "visual studio code",
           "zap": "whatsapp", "whats": "whatsapp", "zapzap": "whatsapp", "navegador": "google chrome", "chrome": "google chrome",
           "edge": "microsoft edge", "word": "word", "excel": "excel", "powerpoint": "powerpoint", "calculadora": "calculadora",
           "calculator": "calculadora", "bloco de notas": "bloco de notas", "notepad": "bloco de notas", "explorer": "explorador de arquivos",
           "explorador": "explorador de arquivos", "arquivos": "explorador de arquivos", "files": "explorador de arquivos",
           "terminal": "terminal", "cmd": "prompt de comando", "teams": "microsoft teams", "lojinha": "microsoft store",
           "loja": "microsoft store", "store": "microsoft store", "spotify": "spotify", "limusic": "limusic"}


def find(query: str) -> dict | None:
    """The installed app the user named ("abre o vscode" -> Visual Studio Code); None when nothing is close enough."""
    q = _norm(query)
    q = re.sub(r"^(o|a|the|el|la|meu|minha|my|mi)\s+", "", q)
    q = re.sub(r"^(app|aplicativo|programa|jogo|game|juego)\s+(do |da |de |of )?", "", q).strip()
    if len(q) < 2:
        return None
    q = ALIASES.get(q, q)
    apps = list_apps()
    names = {_norm(a["name"]): a for a in apps}
    if q in names:
        return {**names[q], "kind": kind(names[q])}
    starts = [a for n, a in names.items() if n.startswith(q + " ") or n.startswith(q)]
    if starts:
        best = min(starts, key=lambda a: len(a["name"]))
        return {**best, "kind": kind(best)}
    words = [a for n, a in names.items() if re.search(rf"\b{re.escape(q)}\b", n)]
    if len(words) == 1 or (words and len(q) >= 4):
        best = min(words, key=lambda a: len(a["name"]))
        return {**best, "kind": kind(best)}
    close = difflib.get_close_matches(q, list(names), n=1, cutoff=0.8)
    if close:
        return {**names[close[0]], "kind": kind(names[close[0]])}
    return None


def launch(app: dict) -> dict:
    app_id = app["id"]
    try:
        if app_id.startswith(("steam://", "http")):
            os.startfile(app_id)
        elif re.match(r"^[a-z]:\\", app_id, re.I) and os.path.exists(app_id):
            os.startfile(app_id)
        else:
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], creationflags=NO_WINDOW)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    from .db import db

    db.log_action("app", f"Abriu {app['name']}")
    return {"ok": True, "name": app["name"], "kind": app.get("kind") or kind(app)}


OPEN_RX = re.compile(r"^\W*(?:(?:ok |ei |hey |oi )?nexus\W+)?(?:pode |por favor |please |can you |puedes )?"
                     r"(?:abr[aei]r?|abre|open|launch|inici[ae]r?|execut[ae]r?|roda|rodar|start|run|"
                     r"(?:vamos |bora |let s |let's )?jog(?:ar|a)|play|ejecuta|lanza)\s+(?:pra mim\s+|para mim\s+|for me\s+)?(.+?)"
                     r"(?:\s+(?:pra mim|para mim|for me|por favor|please))?\W*$", re.I)


def detect(text: str) -> dict | None:
    """'abre o Discord' -> the app (only names that exist on this PC; the NEXUS menus are recognised before this)."""
    m = OPEN_RX.match(text.strip())
    if not m or len(m.group(1).split()) > 6:
        return None
    if re.match(r"^(play|jog)", _norm(text.split()[0] if text.split() else "")) and not find(m.group(1)):
        return None
    app = find(m.group(1))
    return app


# ---------------------------------------------------------------- games started outside NEXUS
def foreground_exe() -> str:
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        return buf.value if ok else ""
    finally:
        kernel32.CloseHandle(handle)


def foreground_game() -> str:
    """Name of the game in the foreground (by its folder: Steam, Epic, Riot, Xbox, emulators, or one the user marked)."""
    exe = foreground_exe()
    if not exe or "nexus" in exe.lower():
        return ""
    base = os.path.splitext(os.path.basename(exe))[0]
    marked = [_norm(n) for n in settings.get("apps_games", [])]
    if GAME_PATH.search(exe) and not NOT_GAME.search(exe) or _norm(base) in marked:
        m = re.search(r"steamapps\\common\\([^\\]+)|epic games\\([^\\]+)|riot games\\([^\\]+)|xboxgames\\([^\\]+)", exe, re.I)
        return next((g for g in (m.groups() if m else ()) if g), base)
    return ""
