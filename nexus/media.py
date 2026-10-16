"""Media control (v0.18.0): play/pause, next, previous, volume and "what's playing" for any player that shows up in
Windows' media controls - Spotify, LiMusic, YouTube in the browser, the Windows player...

The keys are the same media keys a keyboard sends (they reach the player Windows considers current); the volume is
the system volume (Core Audio); "what's playing" reads the Windows media sessions (SMTC) through PowerShell, ~0.4 s.
Recognised phrases are handled instantly, without the model."""
import ctypes
import json
import re
import subprocess
import time
import unicodedata

VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2, "mute": 0xAD, "volume_down": 0xAE,
      "volume_up": 0xAF}
NO_WINDOW = 0x08000000


def _key(vk: int):
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP


# ---------------------------------------------------------------- system volume (Core Audio)
_endpoint = None


def _volume_iface():
    """IAudioEndpointVolume of the default output device (the interfaces declared by hand: no extra package)."""
    global _endpoint
    if _endpoint is not None:
        return _endpoint
    from ctypes import HRESULT, POINTER, c_float, c_uint, c_void_p
    from ctypes.wintypes import BOOL, DWORD

    import comtypes
    from comtypes import COMMETHOD, GUID, IUnknown

    class IAudioEndpointVolume(IUnknown):
        _iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
        _methods_ = [
            COMMETHOD([], HRESULT, "RegisterControlChangeNotify", (["in"], c_void_p, "p")),
            COMMETHOD([], HRESULT, "UnregisterControlChangeNotify", (["in"], c_void_p, "p")),
            COMMETHOD([], HRESULT, "GetChannelCount", (["out"], POINTER(c_uint), "n")),
            COMMETHOD([], HRESULT, "SetMasterVolumeLevel", (["in"], c_float, "db"), (["in"], POINTER(GUID), "ctx")),
            COMMETHOD([], HRESULT, "SetMasterVolumeLevelScalar", (["in"], c_float, "level"), (["in"], POINTER(GUID), "ctx")),
            COMMETHOD([], HRESULT, "GetMasterVolumeLevel", (["out"], POINTER(c_float), "db")),
            COMMETHOD([], HRESULT, "GetMasterVolumeLevelScalar", (["out"], POINTER(c_float), "level")),
            COMMETHOD([], HRESULT, "SetChannelVolumeLevel", (["in"], c_uint, "ch"), (["in"], c_float, "db"),
                      (["in"], POINTER(GUID), "ctx")),
            COMMETHOD([], HRESULT, "SetChannelVolumeLevelScalar", (["in"], c_uint, "ch"), (["in"], c_float, "level"),
                      (["in"], POINTER(GUID), "ctx")),
            COMMETHOD([], HRESULT, "GetChannelVolumeLevel", (["in"], c_uint, "ch"), (["out"], POINTER(c_float), "db")),
            COMMETHOD([], HRESULT, "GetChannelVolumeLevelScalar", (["in"], c_uint, "ch"), (["out"], POINTER(c_float), "level")),
            COMMETHOD([], HRESULT, "SetMute", (["in"], BOOL, "mute"), (["in"], POINTER(GUID), "ctx")),
            COMMETHOD([], HRESULT, "GetMute", (["out"], POINTER(BOOL), "mute")),
        ]

    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Activate", (["in"], POINTER(GUID), "iid"), (["in"], DWORD, "ctx"),
                      (["in"], c_void_p, "params"), (["out"], POINTER(POINTER(IUnknown)), "out")),
        ]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints", (["in"], DWORD, "flow"), (["in"], DWORD, "mask"),
                      (["out"], POINTER(c_void_p), "devices")),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint", (["in"], DWORD, "flow"), (["in"], DWORD, "role"),
                      (["out"], POINTER(POINTER(IMMDevice)), "device")),
        ]

    comtypes.CoInitialize()
    enum = comtypes.CoCreateInstance(GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}"), IMMDeviceEnumerator,
                                     comtypes.CLSCTX_ALL)
    device = enum.GetDefaultAudioEndpoint(0, 1)  # eRender, eMultimedia
    unknown = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    _endpoint = unknown.QueryInterface(IAudioEndpointVolume)
    return _endpoint


def get_volume() -> dict:
    try:
        ep = _volume_iface()
        return {"volume": round(ep.GetMasterVolumeLevelScalar() * 100), "muted": bool(ep.GetMute())}
    except Exception as exc:  # no output device / COM unavailable
        _reset()
        return {"error": f"volume unavailable: {type(exc).__name__}"}


def set_volume(pct: int) -> dict:
    pct = max(0, min(100, int(pct)))
    try:
        ep = _volume_iface()
        ep.SetMasterVolumeLevelScalar(pct / 100, None)
        if pct > 0 and ep.GetMute():
            ep.SetMute(False, None)
        return {"volume": pct}
    except Exception:
        _reset()
        # fallback: the volume keys (2% per press)
        for _ in range(50):
            _key(VK["volume_down"])
        for _ in range(pct // 2):
            _key(VK["volume_up"])
        return {"volume": pct, "approx": True}


def set_mute(on: bool) -> dict:
    try:
        _volume_iface().SetMute(bool(on), None)
    except Exception:
        _reset()
        _key(VK["mute"])
    return {"muted": bool(on)}


def _reset():
    global _endpoint
    _endpoint = None


# ---------------------------------------------------------------- what's playing (SMTC)
_PS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(3000) | Out-Null; $task.Result }
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime] | Out-Null
$m = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$cur = $m.GetCurrentSession()
$out = @()
foreach ($s in $m.GetSessions()) {
  $p = Await ($s.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
  $out += [pscustomobject]@{ app = $s.SourceAppUserModelId; title = $p.Title; artist = $p.Artist; album = $p.AlbumTitle;
    status = $s.GetPlaybackInfo().PlaybackStatus.ToString(); current = ($cur -ne $null -and $s.SourceAppUserModelId -eq $cur.SourceAppUserModelId) }
}
ConvertTo-Json -Compress -InputObject @($out)
"""
APP_NAMES = [(r"spotify", "Spotify"), (r"limusic", "LiMusic"), (r"chrome", "Google Chrome"), (r"msedge|edge", "Microsoft Edge"),
             (r"brave", "Brave"), (r"firefox", "Firefox"), (r"opera", "Opera"), (r"zunemusic|mediaplayer", "Media Player"),
             (r"vlc", "VLC"), (r"deezer", "Deezer"), (r"tidal", "TIDAL"), (r"applemusic|itunes", "Apple Music"),
             (r"youtube", "YouTube Music")]


def app_name(app_id: str) -> str:
    low = (app_id or "").lower()
    return next((name for rx, name in APP_NAMES if re.search(rx, low)), (app_id or "?").split("!")[0].split("\\")[-1])


def now_playing() -> dict:
    """{"playing": [{"app", "title", "artist", "status"}...], "current": {...} | None}."""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS], capture_output=True,
                             text=True, timeout=8, creationflags=NO_WINDOW, encoding="utf-8", errors="replace").stdout.strip()
        sessions = json.loads(out) if out else []
    except (subprocess.SubprocessError, OSError, ValueError):
        return {"error": "media sessions unavailable"}
    if isinstance(sessions, dict):
        sessions = [sessions]
    items = [{"app": app_name(s.get("app", "")), "title": s.get("title") or "", "artist": s.get("artist") or "",
              "album": s.get("album") or "", "status": (s.get("status") or "").lower(), "current": bool(s.get("current"))}
             for s in sessions if s.get("title")]
    current = next((s for s in items if s["status"] == "playing"), None) or next((s for s in items if s["current"]), None)
    return {"sessions": items, "current": current}


# ---------------------------------------------------------------- actions
def control(action: str, level: int | None = None) -> dict:
    """play_pause / play / pause / next / previous / stop / volume_up / volume_down / volume (level) / mute / unmute /
    now_playing."""
    if action == "now_playing":
        return now_playing()
    if action in ("play", "pause"):
        np = now_playing()
        cur = np.get("current") or {}
        playing = cur.get("status") == "playing"
        if (action == "pause") == playing:  # toggle only when it changes something
            _key(VK["play_pause"])
        return {"ok": True, "action": action, "app": cur.get("app", "")}
    if action in ("play_pause", "next", "previous", "stop"):
        _key(VK[action])
        return {"ok": True, "action": action}
    if action == "volume":
        return set_volume(level if level is not None else 50)
    if action in ("volume_up", "volume_down"):
        vol = get_volume()
        if "error" in vol:
            for _ in range(5):
                _key(VK[action])
            return {"ok": True, "action": action}
        step = int(level or 10)
        return set_volume(vol["volume"] + (step if action == "volume_up" else -step))
    if action in ("mute", "unmute"):
        return set_mute(action == "mute")
    return {"error": f"unknown media action {action}"}


# ---------------------------------------------------------------- phrases (instant, no model)
def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9% ]+", " ", text)
    text = re.sub(r"^\s*(ok |ei |hey |oi )?nexus\s+", "", text)
    text = re.sub(r"^\s*(pode |por favor |please |can you |could you |puedes |podrias )+", "", text)
    return re.sub(r"\s+", " ", text).strip()


MEDIA = r"(musicas?|som|audio|cancao|cancoes|songs?|music|tracks?|faixas?|spotify|limusic|youtube|player|videos?|cancion(es)?|tema)"
PHRASES = [
    ("now_playing", re.compile(r"\b(que musica e essa|qual (e )?(a )?musica|o que (esta|ta) tocando|qual musica (esta|ta) tocando|"
                               r"what s playing|whats playing|what is playing|what song is this|what song is playing|"
                               r"que cancion es esta|que (esta )?sonando|que suena)\b")),
    ("pause", re.compile(rf"^(pausa|pause|pausar|pausa ai|para|parar|stop|deten|detener|pare)( a| o| the| la| el| essa| esta| this)? {MEDIA}\b")),
    ("play", re.compile(rf"^((continua|continuar|retoma|retomar|despausa|resume|unpause|reanuda|sigue|solta|volta a tocar|"
                        rf"da play|de play|dar play|play|press play)( (a|o|the|la|el|na|no))? ?{MEDIA}?|"
                        rf"(volta|voltar) (a|o) {MEDIA})$")),
    ("next", re.compile(rf"^((proxima|proximo|pula|pular|passa|passar|avanca|avancar|skip|next|siguiente|salta|saltar|cambia)"
                        rf"( (a|o|essa|esta|this|the|la|el|de|pra))?( {MEDIA})?|{MEDIA} (seguinte|siguiente))$")),
    ("previous", re.compile(rf"^({MEDIA} anterior|(volta|voltar) (uma|a) {MEDIA} (anterior)?|previous( {MEDIA})?|"
                            rf"(go )?back( a| one)? {MEDIA}|last {MEDIA}|anterior)$")),
    ("mute", re.compile(r"^(muta|mutar|silencia|silenciar|mute|tira o som|tirar o som|sem som|quita el sonido)( (o|a|the|el) )?"
                        r"( ?(som|audio|computador|pc|volume|sound|sonido))?$")),
    ("unmute", re.compile(r"^(desmuta|desmutar|unmute|volta o som|ativa o som|liga o som|turn the sound on|activa el sonido)$")),
    ("volume", re.compile(r"\b(volume|som|audio|sound|sonido|volumen)\s+(em|para|pra|no|a|to|at|al|en)\s+(\d{1,3})\s*(%|por cento|percent|por ciento)?\b")),
    ("volume_up", re.compile(r"^(aumenta|aumentar|sobe|subir|mais alto|turn up|louder|raise|sube|subele|aumenta el)( (o|a|the|el))?"
                             r"( (volume|som|audio|sound|sonido|volumen))?( (um pouco|a bit|un poco))?$")),
    ("volume_down", re.compile(r"^(abaixa|abaixar|diminui|diminuir|baixa|baixar|mais baixo|turn down|quieter|lower|baja|bajale)"
                               r"( (o|a|the|el))?( (volume|som|audio|sound|sonido|volumen))?( (um pouco|a bit|un poco))?$")),
]
# volume up/down alone ("aumenta") need the word volume/som: these are what to accept without it
NEEDS_OBJECT = {"volume_up", "volume_down"}


def detect(text: str) -> dict | None:
    norm = _norm(text)
    if not norm or len(norm.split()) > 10:
        return None
    for action, rx in PHRASES:
        m = rx.search(norm)
        if not m:
            continue
        if action in NEEDS_OBJECT and not re.search(r"\b(volume|som|audio|sound|sonido|volumen)\b", norm):
            continue
        if action == "previous" and norm == "anterior":
            continue
        out = {"action": action}
        if action == "volume":
            out["level"] = int(m.group(3))
        return out
    return None


TEXTS = {
    "pt": {"pause": "Pausei.", "play": "Continuando.", "next": "Próxima.", "previous": "Voltando uma.", "mute": "Som desligado.",
           "unmute": "Som ligado.", "volume": "Volume em {v}%.", "volume_up": "Volume em {v}%.", "volume_down": "Volume em {v}%.",
           "playing": "Tocando agora: {title}{artist} ({app}).", "paused_item": "Pausado: {title}{artist} ({app}).",
           "nothing": "Nada está tocando agora.", "by": " — "},
    "en": {"pause": "Paused.", "play": "Resuming.", "next": "Next one.", "previous": "Going back one.", "mute": "Sound off.",
           "unmute": "Sound on.", "volume": "Volume at {v}%.", "volume_up": "Volume at {v}%.", "volume_down": "Volume at {v}%.",
           "playing": "Now playing: {title}{artist} ({app}).", "paused_item": "Paused: {title}{artist} ({app}).",
           "nothing": "Nothing is playing right now.", "by": " — "},
    "es": {"pause": "Pausado.", "play": "Continuando.", "next": "Siguiente.", "previous": "Volviendo una.", "mute": "Sonido apagado.",
           "unmute": "Sonido activado.", "volume": "Volumen al {v}%.", "volume_up": "Volumen al {v}%.", "volume_down": "Volumen al {v}%.",
           "playing": "Sonando ahora: {title}{artist} ({app}).", "paused_item": "En pausa: {title}{artist} ({app}).",
           "nothing": "No está sonando nada ahora.", "by": " — "},
}


def reply(action: str, result: dict, code: str) -> str:
    T = TEXTS.get(code, TEXTS["pt"])
    if action == "now_playing":
        cur = result.get("current")
        if not cur:
            return T["nothing"]
        key = "playing" if cur["status"] == "playing" else "paused_item"
        return T[key].format(title=cur["title"], artist=(T["by"] + cur["artist"]) if cur["artist"] else "", app=cur["app"])
    if action.startswith("volume"):
        return T[action].format(v=result.get("volume", "?"))
    return T.get(action, "OK.")


def handle(text: str, code: str) -> tuple[dict, str] | None:
    """Instant path used by the assistant: (result, reply) for a recognised phrase, else None."""
    cmd = detect(text)
    if not cmd:
        return None
    t0 = time.perf_counter()
    result = control(cmd["action"], cmd.get("level"))
    result["ms"] = round((time.perf_counter() - t0) * 1000)
    return {**cmd, **result}, reply(cmd["action"], result, code)
