"""Text-to-speech: Windows SAPI voices (Desktop + OneCore) rendered to memory, then processed with a
voice effect ("jarvis" / "robot") and played with sounddevice.

All SAPI objects live in the thread that created them (call `Engine()` inside the speaker thread)."""
import re
from xml.sax.saxutils import escape

import numpy as np

RATE = 22050
CATEGORIES = (
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",  # e.g. "Microsoft Daniel" (pt-BR, male)
)
# SAPI "Language" attribute = hex LCID(s), e.g. "416" (pt-BR), "409" (en-US), "c0a" (es-ES).
LCID = {"416": "pt", "816": "pt", "409": "en", "809": "en", "c09": "en", "1009": "en",
        "c0a": "es", "40a": "es", "80a": "es", "2c0a": "es", "540a": "es"}
FALLBACK_PITCH = {"male": -8, "female": 6}  # pitch shift when the requested gender isn't installed


class Voice:
    def __init__(self, token, name, gender, lang):
        self.token, self.name, self.gender, self.lang = token, name, gender, lang

    def as_dict(self):
        return {"name": self.name, "gender": self.gender, "lang": self.lang}


class Engine:
    def __init__(self):
        import comtypes
        import comtypes.client

        comtypes.CoInitialize()
        self._client = comtypes.client
        self._sapi = comtypes.client.CreateObject("SAPI.SpVoice")
        self.voices = self._enumerate()

    def _enumerate(self) -> list[Voice]:
        found, seen = [], set()
        for path in CATEGORIES:
            try:
                cat = self._client.CreateObject("SAPI.SpObjectTokenCategory")
                cat.SetId(path, False)
                tokens = cat.EnumerateTokens()
            except Exception:
                continue
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                name = tok.GetAttribute("Name") or ""
                base = name.replace(" Desktop", "")
                if base in seen:  # "Maria Desktop" and OneCore "Maria" are the same voice
                    continue
                seen.add(base)
                codes = [c.strip().lower() for c in (tok.GetAttribute("Language") or "").split(";")]
                lang = next((LCID[c] for c in codes if c in LCID), None)
                gender = (tok.GetAttribute("Gender") or "").lower() or "female"
                found.append(Voice(tok, base, gender, lang))
        return found

    def pick(self, lang: str, gender: str) -> tuple[Voice | None, int]:
        """Best voice for language+gender and the pitch offset to apply (fallback when gender missing)."""
        same_lang = [v for v in self.voices if v.lang == lang]
        for v in same_lang:
            if v.gender == gender:
                return v, 0
        if same_lang:
            return same_lang[0], FALLBACK_PITCH.get(gender, 0)
        exact = [v for v in self.voices if v.gender == gender]
        if exact:
            return exact[0], 0
        return (self.voices[0], FALLBACK_PITCH.get(gender, 0)) if self.voices else (None, 0)

    def render(self, text: str, voice: Voice | None, pitch: int = 0, speed: int = 0) -> np.ndarray:
        """Synthesize to a float32 mono array at RATE Hz."""
        if voice is not None:
            self._sapi.Voice = voice.token
        stream = self._client.CreateObject("SAPI.SpMemoryStream")
        fmt = self._client.CreateObject("SAPI.SpAudioFormat")
        fmt.Type = 22  # SAFT22kHz16BitMono
        stream.Format = fmt
        self._sapi.AudioOutputStream = stream
        xml = f'<rate absspeed="{speed}"><pitch absmiddle="{pitch}">{escape(text)}</pitch></rate>'
        self._sapi.Speak(xml, 8)  # SVSFIsXML
        return np.frombuffer(bytes(stream.GetData()), dtype=np.int16).astype(np.float32) / 32768.0


# ---------------------------------------------------------------- effects
def _band(x: np.ndarray, low: float, high: float) -> np.ndarray:
    """Zero-phase band-pass via FFT (smooth 1-octave-ish roll-off)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    gain = 1 / (1 + (low / np.maximum(f, 1)) ** 4) / (1 + (f / high) ** 4)
    return np.fft.irfft(spec * gain, len(x))


def _taps(x: np.ndarray, taps) -> np.ndarray:
    """Sum of delayed copies: [(delay_seconds, gain), ...]."""
    out = x.copy()
    for delay, gain in taps:
        d = int(delay * RATE)
        out[d:] += gain * x[: len(x) - d]
    return out


def _eq(x: np.ndarray, high_pass: float, presence_db: float, center: float = 3200, width_oct: float = 1.2,
        low_pass: float = 10000) -> np.ndarray:
    """Zero-phase EQ via FFT: high-pass + a bell boost in the consonant range (clarity) + gentle top roll-off."""
    spec = np.fft.rfft(x)
    f = np.maximum(np.fft.rfftfreq(len(x), 1 / RATE), 1.0)
    hp = 1 / np.sqrt(1 + (high_pass / f) ** 4)
    lp = 1 / np.sqrt(1 + (f / low_pass) ** 8)
    bell = 10 ** (presence_db / 20 * np.exp(-0.5 * (np.log2(f / center) / (width_oct / 2)) ** 2))
    return np.fft.irfft(spec * hp * lp * bell, len(x))


def apply_effect(x: np.ndarray, effect: str) -> np.ndarray:
    """Voice colour. "jarvis" must stay perfectly intelligible: no ring modulation (it made the voice buzz
    like an electrolarynx) and no band-limiting of consonants; only presence, a faint digital sheen and room."""
    if effect == "none" or len(x) == 0:
        return x
    x = np.concatenate([x, np.zeros(int(0.2 * RATE), np.float32)])  # room for the echoes
    if effect == "robot":
        t = np.arange(len(x)) / RATE
        x = 0.6 * x + 0.4 * x * np.sin(2 * np.pi * 70 * t)                  # ring modulation (the robot buzz)
        x = _taps(x, [(0.005, 0.45), (0.010, 0.2)])                          # metallic comb
        x = _band(x, 180, 6000)
    else:  # "jarvis"
        x = _eq(x, high_pass=90, presence_db=4.0)                            # clarity: consonants 2-5 kHz up
        x = x + 0.10 * np.roll(x, int(0.0012 * RATE))                        # faint digital sheen (1.2 ms)
        x = _taps(x, [(0.023, 0.07), (0.037, 0.045)])                        # small, dry room
    peak = float(np.max(np.abs(x))) or 1.0
    return (x / peak * 0.9).astype(np.float32)


# The name is pronounced "NÉCSUS" (open E, "NÉ-QUI-SÚS"). Portuguese/Spanish voices read "Nexus" as "NÊXUS" and spell
# "N.E.X.U.S" letter by letter, so the spoken text uses an accented spelling (the screen keeps N.E.X.U.S).
_NAME = re.compile(r"\bN\.E\.X\.U\.S\b|\bnexus\b", re.IGNORECASE)
_SPOKEN_NAME = {"pt": "Nécsus", "es": "Nécsus", "en": "Nexus"}  # NÉCSUS / NÉ-QUI-SÚS


def pronounce(text: str, lang: str) -> str:
    return _NAME.sub(_SPOKEN_NAME.get(lang, "Nexus"), text)


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?;:])\s+", text) if s.strip()]
