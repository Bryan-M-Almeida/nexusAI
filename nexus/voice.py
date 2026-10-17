"""Offline voice: faster-whisper speech-to-text + Windows SAPI text-to-speech with effects (tts.py)."""
import pathlib
import queue
import re
import unicodedata
import threading
import time

import numpy as np

from .config import settings
from .i18n import LANGS, detect, lang

RATE = 16000
FRAME = 512  # 32 ms: the window Silero VAD expects at 16 kHz
FRAMES_PER_SECOND = RATE / FRAME
# "Nexus" as Whisper tends to write it in pt/en/es: nexus, néxus, nécsus, neksus, nexos, nexis, next us, nex us...
WAKE_RE = re.compile(r"\b(n[eéêiy]?[xk]+s?[ iuoe]*[sz]|n[eé]c?k?s[uo]s|nexo|next? ?us|nex us|nek us)\b[\s,.!?:;-]*",
                     re.IGNORECASE)
ENV_STEP = 0.04  # seconds per point of the speech envelope sent to the UI ring
ECHO_TAIL = 2.5   # v0.18.1: an utterance starting this soon after NEXUS went quiet may be its own voice (mic delay)
ECHO_WINDOW = 12  # v0.18.1: seconds after NEXUS speaks in which its own words coming back are ignored
MAX_CONTROL_SECONDS = 4  # while NEXUS speaks, only short utterances ("pausa", "stop") are considered


URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]\"']+", re.IGNORECASE)
_TLD_PARTS = {"com", "org", "net", "gov", "edu", "br", "co", "uk", "io", "app", "dev", "info", "es", "pt", "mx",
              "ar", "us", "me", "tv", "ai", "www", "m"}


def site_name(url: str) -> str:
    """https://pt.wikipedia.org/wiki/X -> "wikipedia"; https://g1.globo.com.br/... -> "globo"."""
    from urllib.parse import urlsplit

    host = urlsplit(url if "://" in url else "http://" + url).hostname or ""
    labels = [x for x in host.lower().split(".") if x]
    while len(labels) > 1 and labels[-1] in _TLD_PARTS:
        labels.pop()
    return labels[-1] if labels else ""


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", " ", text)  # inline code / file paths are shown, not read aloud
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # markdown link: only its text
    # A raw link is spoken as the site's name instead of letter by letter (v0.14).
    def spoken(m):
        url = m.group(0).rstrip(".,;:!?")
        return (site_name(url) or " ") + m.group(0)[len(url):]  # keep the sentence's own punctuation

    text = URL_RE.sub(spoken, text)
    text = re.sub(r"[*_`#>|]", "", text)
    # v0.18.1: emojis and pictographs are shown, not read aloud (SAPI read "😄" as "cara sorrindo de boca aberta")
    text = "".join(" " if unicodedata.category(c) in ("So", "Sk", "Cs") or c in "\u200d\ufe0f\u20e3" else c for c in text)
    return re.sub(r"\s+", " ", text).strip()


# -- v0.18.1: what the microphone hears that isn't the user -----------------------------------------------------------
HALLUCINATIONS = re.compile(r"legendas? (pela|por|da) comunidade|amara\.org|obrigad[oa] por assistir|inscreva-se|"
                            r"se inscrev[ae]|ative o sininho|thanks? (you )?for watching|subtitles by|please subscribe|"
                            r"subt[ií]tulos (realizados|por|de la comunidad)|gracias por ver|suscr[ií]bete", re.I)


def _words(text: str, min_len: int = 3) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return [w for w in re.findall(r"[a-z0-9]+", text) if len(w) >= min_len]


def is_echo(text: str, recent_speech: str, right_after: bool = True) -> bool:
    """The transcript is NEXUS's own voice coming back through the microphone (loudspeakers, or a microphone with
    delay like DroidCam over Wi-Fi): a run of at least 4 words NEXUS just said, making up half of what was heard.
    A reply that reuses a few of its words ("conta uma piada" after "posso contar uma piada") is not echo, and later
    than ECHO_TAIL after NEXUS went quiet only an almost literal repetition counts (choosing one of the options it
    offered - "jogar um jogo de perguntas" - is an answer)."""
    import difflib

    words, spoken = _words(text, 1), _words(recent_speech, 1)
    if len(words) < 4 or not spoken:
        return False
    m = difflib.SequenceMatcher(None, words, spoken, autojunk=False).find_longest_match(0, len(words), 0, len(spoken))
    if right_after:
        return m.size >= 4 and m.size / len(words) >= 0.5
    return m.size >= 8 and m.size / len(words) >= 0.9


def is_hallucination(text: str) -> bool:
    """Whisper inventing speech on noise: subtitle credits, or the same sentence over and over
    ("Você tem um clima? Você tem um clima? Você tem um clima?")."""
    if HALLUCINATIONS.search(text):
        return True
    parts = [re.sub(r"\W+", " ", x).strip().lower() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    if len(parts) >= 3:
        top = max(set(parts), key=parts.count)
        return parts.count(top) >= 3 and len(top.split()) >= 2  # "Sim. Sim. Pode marcar às dez." is a real answer
    words = text.lower().split()
    return len(words) >= 6 and len(set(words)) <= len(words) // 3


def speech_allowed() -> bool:
    """NEXUS talks only in audio mode and when the AI voice isn't muted."""
    return settings["ui_mode"] == "audio" and settings["voice_enabled"]


class Speaker:
    """Speaks sentence by sentence on its own thread. Supports stop, pause/resume and repeat.

    on_state(state): "speaking" | "paused" | "idle"
    on_audio(payload): {"env": [...0..1], "dt": seconds} sent when each sentence starts playing,
                       so the UI ring can follow the voice locally without streaming levels."""

    def __init__(self, on_state, on_audio=lambda payload: None):
        self.on_state, self.on_audio = on_state, on_audio
        self.q: queue.Queue = queue.Queue()
        self.speaking = threading.Event()
        self.interrupt = threading.Event()
        self.paused = threading.Event()
        self._resume = threading.Event()
        self.last_text = ""
        self.recent: list[tuple[float, str]] = []  # v0.18.1: (time, text) spoken lately - the echo check compares
        self.ended_at = 0.0                         # when the voice last went quiet
        self.voices: list[dict] = []
        self.error: str | None = None
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True, name="tts").start()

    # -- control -------------------------------------------------------------
    def say(self, text: str, force: bool = False, remember: bool = True, lang_code: str | None = None,
            on_done=None):
        """Queue text. The voice follows the text's language (pt/en/es), else the app language."""
        text = clean_for_speech(text)
        if not text or not (speech_allowed() or force):
            return
        if remember:
            self.last_text = text
        self.interrupt.clear()
        self.q.put((text, lang_code, on_done))  # on_done(): called only if the text was spoken to the end

    def recent_speech(self) -> str:
        """What NEXUS said in the last ECHO_WINDOW seconds (empty when it has been quiet for that long)."""
        now = time.time()
        if not self.speaking.is_set() and now - self.ended_at > ECHO_WINDOW:
            return ""
        return " ".join(x for t, x in self.recent if now - t < ECHO_WINDOW + 60)

    def repeat(self, intro: str = ""):
        if not self.last_text:
            return False
        self.stop()
        if intro:
            self.say(intro, force=True, remember=False)
        self.say(self.last_text, force=True)
        return True

    def pause(self) -> bool:
        if not self.speaking.is_set() or self.paused.is_set():
            return False
        self.paused.set()
        self._sd().stop()
        return True

    def resume(self) -> bool:
        if not self.paused.is_set():
            return False
        self.paused.clear()
        self._resume.set()
        return True

    def stop(self):
        self.interrupt.set()
        while not self.q.empty():
            self.q.get_nowait()
        self.paused.clear()
        self._resume.set()  # release a paused playback so it can exit
        self._sd().stop()

    def list_voices(self) -> list[dict]:
        self._ready.wait(5)
        return self.voices

    @staticmethod
    def _sd():
        import sounddevice as sd

        return sd

    # -- worker --------------------------------------------------------------
    @staticmethod
    def _envelope(audio: np.ndarray, rate: int) -> list[float]:
        step = max(1, int(rate * ENV_STEP))
        n = len(audio) // step
        if n == 0:
            return []
        rms = np.sqrt(np.mean(audio[: n * step].reshape(n, step) ** 2, axis=1))
        return np.round(rms / (rms.max() or 1), 2).tolist()

    # v0.14: short sentences that repeat (greeting, "Running in ... mode", reminders, "I'll repeat") are
    # synthesized once and reused; SAPI rendering + effects cost ~100-300 ms per sentence.
    CACHE_MAX, CACHE_CHARS = 48, 160

    def _render(self, engine, tts, sentence, voice, pitch):
        key = (sentence, getattr(voice, "name", ""), pitch, settings["tts_speed"], settings["voice_effect"])
        cache = self.__dict__.setdefault("_cache", {})
        if key in cache:
            self.cache_hits = getattr(self, "cache_hits", 0) + 1
            audio = cache.pop(key)
            cache[key] = audio  # most recently used goes last
            return audio
        audio = tts.apply_effect(engine.render(sentence, voice, pitch, settings["tts_speed"]), settings["voice_effect"])
        if len(sentence) <= self.CACHE_CHARS:
            cache[key] = audio
            while len(cache) > self.CACHE_MAX:
                cache.pop(next(iter(cache)))
        return audio

    def _run(self):
        from . import tts

        sd = self._sd()
        try:
            engine = tts.Engine()
        except Exception as exc:  # no SAPI (non-Windows) -> app keeps working silently
            self.error = str(exc)
            self._ready.set()
            return
        self.voices = [v.as_dict() for v in engine.voices]
        self._ready.set()
        while True:
            text, code, on_done = self.q.get()
            code = code or detect(text) or lang()  # streamed chunks carry the reply language: no voice flips
            voice, pitch = engine.pick(code, settings["voice_gender"])
            self.speaking.set()
            self.on_state("speaking")
            spoken = tts.pronounce(text, code, voice.gender if voice else "male")
            now = time.time()
            self.recent = [(t, x) for t, x in self.recent if now - t < ECHO_WINDOW] + [(now, text + " " + spoken)]
            sentences, i = tts.split_sentences(spoken), 0
            try:
                while i < len(sentences) and not self.interrupt.is_set():
                    if self.paused.is_set():  # wait for resume(); the cut sentence is replayed
                        self.on_state("paused")
                        self._resume.wait()
                        self._resume.clear()
                        if self.interrupt.is_set():
                            break
                        self.on_state("speaking")
                    audio = self._render(engine, tts, sentences[i], voice, pitch)
                    audio = audio * (max(0, min(100, int(settings["tts_volume"]))) / 100)  # Settings > Voice volume
                    self.on_audio({"env": self._envelope(audio, tts.RATE), "dt": ENV_STEP})
                    sd.play(audio, tts.RATE)
                    sd.wait()
                    if not self.paused.is_set():
                        i += 1
            except Exception as exc:
                self.error = str(exc)
            if on_done and i >= len(sentences) and not self.interrupt.is_set():
                try:
                    on_done()  # e.g. the podcast queues its next part here, so the voice never goes idle in between
                except Exception as exc:
                    self.error = str(exc)
            if self.q.empty():
                time.sleep(0.25)  # let the room echo die before the mic goes back to full listening
                self.ended_at = time.time()
                self.speaking.clear()
                self.on_state("idle")


def bundled_model(name: str) -> pathlib.Path | None:
    """The voice model folder that ships inside NEXUS (build_whisper.py), when this size is the bundled one."""
    import sys

    roots = [pathlib.Path(getattr(sys, "_MEIPASS", "")) / "whisper"] if getattr(sys, "frozen", False) else []
    roots.append(pathlib.Path(__file__).resolve().parent.parent / "whisper")
    for root in roots:
        if (root / name / "model.bin").exists():
            return root / name
    return None


def initial_prompt(name: str = "") -> str:
    """Short text that biases Whisper toward the assistant's vocabulary (wake word, user name)."""
    who = f" {name}" if name else ""
    return {"pt": f"NEXUS, assistente de voz.{who}", "en": f"NEXUS, voice assistant.{who}",
            "es": f"NEXUS, asistente de voz.{who}"}.get(lang(), f"NEXUS.{who}").strip()


def normalize_audio(audio: np.ndarray, target: float = 0.5, max_gain: float = 8.0) -> np.ndarray:
    """Peak-normalizes a quiet utterance (low-gain microphones), without amplifying pure noise too much."""
    audio = audio - float(np.mean(audio))  # remove DC offset (cheap USB/HDA mics)
    peak = float(np.abs(audio).max()) if len(audio) else 0.0
    if peak <= 1e-4:
        return audio.astype(np.float32)
    return (audio * min(max_gain, target / peak)).astype(np.float32)


class SpeechDetector:
    """Streaming end-of-speech detector. Uses the Silero VAD bundled with faster-whisper (a neural
    voice detector, ~0.2 ms per 32 ms frame) so fans and room noise no longer keep the recording open;
    falls back to an adaptive energy threshold if the model can't be loaded.

    feed(frame of 512 samples) -> None | "start" | "speech" | "end"; .audio holds the utterance after "end"."""

    START_FRAMES = 3      # ~100 ms of voice opens a segment
    PRE_ROLL = 10         # ~320 ms kept before the start (first syllable)
    END_SILENCE = 0.7     # seconds of non-voice that close the segment
    ON, OFF = 0.5, 0.35   # hysteresis on the speech probability
    _session = None

    def __init__(self, max_seconds: float = 30):
        self.max_frames = int(max_seconds * FRAMES_PER_SECOND)
        self.session = self._load()
        self.configure()
        self.reset()

    def configure(self):
        """Sensitivity and end-of-speech pause from Settings > Microphone (read again for every utterance)."""
        self.ON = min(0.9, max(0.2, float(settings.get("vad_threshold", 0.5))))
        self.OFF = self.ON * 0.7
        silence = min(3.0, max(0.3, float(settings.get("vad_silence", self.END_SILENCE))))
        self.end_frames = int(silence * FRAMES_PER_SECOND)

    @classmethod
    def _load(cls):
        if cls._session is None:
            try:
                from faster_whisper.vad import get_vad_model

                cls._session = get_vad_model().session
            except Exception:
                cls._session = False
        return cls._session or None

    def reset(self):
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros(64, dtype=np.float32)
        self.floor, self.voiced, self.silence = 0.003, 0, 0
        self.pre: list = []
        self.buf: list | None = None
        self.audio = None
        self.prob = 0.0

    def probability(self, frame: np.ndarray) -> float:
        if self.session is None:  # energy fallback
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if self.buf is None and rms <= max(self.floor * 3.0, 0.008):
                self.floor = 0.95 * self.floor + 0.05 * rms
            return 1.0 if rms > max(self.floor * 3.0, 0.008) else 0.0
        x = np.concatenate([self.context, frame]).astype(np.float32)[None, :]
        self.context = frame[-64:].astype(np.float32)
        out, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c})
        return float(np.asarray(out).ravel()[0])

    @property
    def active(self) -> bool:
        return self.buf is not None

    def feed(self, frame: np.ndarray):
        if len(frame) != FRAME:
            return None
        self.prob = p = self.probability(frame)
        if self.buf is None:
            self.pre = (self.pre + [frame])[-self.PRE_ROLL:]
            self.voiced = self.voiced + 1 if p >= self.ON else 0
            if self.voiced >= self.START_FRAMES:
                self.buf, self.silence = list(self.pre), 0
                return "start"
            return None
        self.buf.append(frame)
        self.silence = 0 if p >= self.OFF else self.silence + 1
        if self.silence >= self.end_frames or len(self.buf) >= self.max_frames:
            audio = np.concatenate(self.buf)
            self.reset_segment()
            self.audio = audio
            return "end"
        return "speech"

    def reset_segment(self):
        self.buf, self.voiced, self.silence, self.pre = None, 0, 0, []
        self.configure()


class Listener:
    """Microphone capture with a neural VAD (SpeechDetector); transcribes each utterance with Whisper.

    Modes: "off" | "ptt" (one utterance, then back) | "live" (continuous conversation).
    on_text(text, during_speech): during_speech=True means NEXUS was talking; the app then only
    accepts control commands (pause/stop/...) from it.
    on_level(0..1): microphone level while the user speaks (for the UI ring)."""

    def __init__(self, on_text, on_state, speaker: Speaker, on_level=lambda level: None, on_progress=lambda pct: None):
        self.on_text, self.on_state, self.speaker, self.on_level = on_text, on_state, speaker, on_level
        self.on_progress = on_progress  # v0.16.8: download progress of the voice model, 0..100 (-1 = failed)
        self._hold: list = []  # audio captured while the talk key is held (v0.16.8, beta)
        self.model = None
        self.model_error = None
        self.model_state = "loading"  # loading | ready | missing (not downloaded yet) | error
        self.mode = "off"
        self.live = False  # continuous listening wanted (audio mode with mic unmuted)
        self.awake_until = 0.0
        self.dropped: list[tuple[str, str]] = []
        self.seg_start = 0.0  # v0.18.1: (reason, text) the microphone heard but wasn't the user
        self.background = False  # window minimized/unfocused (v0.14): only "Nexus ..." is accepted
        self.released = False  # Whisper freed while minimized (reloaded when the window comes back)
        self._stream = None
        self._frames: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        threading.Thread(target=self._load_model, daemon=True, name="stt-load").start()
        threading.Thread(target=self._loop, daemon=True, name="stt").start()

    # -- model -------------------------------------------------------------
    def _load_model(self, download=False):
        """Load Whisper from the local cache; only download (~75-1500 MB) when voice is actually used."""
        self.model_state, self.model_error = "loading", None
        try:
            from faster_whisper import WhisperModel

            from . import netprobe

            if download and netprobe.effective() == "offline":
                raise RuntimeError("offline mode: the voice model can't be downloaded (Settings > Performance)")
            watch = threading.Event()
            if download:
                threading.Thread(target=self._watch_download, args=(watch,), daemon=True, name="stt-dl").start()
            try:
                bundled = bundled_model(settings["stt_model"])  # v0.19.0: shipped with NEXUS - no download
                self.model = WhisperModel(str(bundled) if bundled else settings["stt_model"], device="cpu",
                                          compute_type="int8", local_files_only=not download)
            finally:
                watch.set()
            self.model_state = "ready"
            if download:
                self.on_progress(100)
            if self.live:  # audio mode was waiting for the model
                self.set_live(True)
        except Exception as exc:
            self.model = None
            self.model_state = "error" if download else "missing"
            self.model_error = str(exc) if download else None
            if download:
                self.on_progress(-1)

    # approximate download size of each faster-whisper model (bytes)
    MODEL_BYTES = {"tiny": 75.6e6, "base": 145e6, "small": 484e6, "medium": 1.53e9, "large-v3": 3.1e9}

    def _watch_download(self, done: threading.Event):
        """Download progress for the ring: the model folder in the Hugging Face cache grows as it downloads."""
        try:
            from huggingface_hub.constants import HF_HUB_CACHE
        except Exception:
            return
        from . import downloads

        name = settings["stt_model"]
        folder = pathlib.Path(HF_HUB_CACHE) / f"models--Systran--faster-whisper-{name}"
        total = self.MODEL_BYTES.get(name, 5e8)
        did = downloads.start("voice", f"whisper {name}", int(total))
        last = -1
        while not done.wait(0.4):
            size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) if folder.exists() else 0
            downloads.update(did, size)
            pct = min(99, int(size * 100 / total))
            if pct != last:
                self.on_progress(pct)
                last = pct
        downloads.finish(did, self.model_state != "error", self.model_error or "")
    def release(self):
        """Free Whisper's memory (~0.5 GB for "small") while voice isn't needed; reloaded on demand."""
        if self.model is not None and self.mode == "off":
            self.model = None
            self.model_state = "missing"
            self.released = True

    def set_background(self, on: bool):
        self.background = bool(on)

    def wake_required(self) -> bool:
        return bool(settings["require_wake_word"] or (self.background and settings["bg_wake_only"]))

    def reload_model(self):
        threading.Thread(target=self._load_model, args=(True,), daemon=True, name="stt-load").start()

    def ensure_model(self) -> bool:
        if self.model_state in ("missing", "error"):
            self.reload_model()
        return self.ready

    @property
    def ready(self):
        return self.model_state == "ready"

    # -- control -----------------------------------------------------------
    def push_to_talk(self):
        self.speaker.stop()
        self.mode = "ptt"
        self._open()
        self.on_state("listening")

    # v0.16.8 (beta): hold the talk key - the microphone records until it is released, then the text is sent
    def hold_start(self):
        self.speaker.stop()
        self._hold = []
        self.mode = "hold"
        self._open()
        self.on_state("listening")

    def hold_stop(self):
        if self.mode != "hold":
            return
        buf, self._hold = self._hold, []
        self.mode = "live" if self.live else "off"
        if not self.live:
            self._close()
        self.on_level(0)
        audio = np.concatenate(buf) if buf else np.zeros(0, dtype=np.float32)
        if len(audio) < RATE * 0.3 or not self.ready:
            self.on_state("standby" if self.mode == "live" else "idle")
            return
        threading.Thread(target=self._handle, args=(audio, False, True), daemon=True, name="stt-hold").start()

    def set_live(self, enabled: bool):
        """Continuous conversation (audio mode, mic unmuted). Starts as soon as Whisper is ready;
        it never triggers the model download by itself (ensure_model() does, on user action)."""
        self.live = enabled
        if enabled and self.ready:
            self.mode = "live"
            self._open()
            self.on_state("standby")
        elif self.mode != "ptt":
            self.mode = "off"
            self._close()
            self.on_state("idle")

    def _open(self):
        with self._lock:
            if self._stream is None:
                import sounddevice as sd

                device = settings["mic_device"] or None  # "" = Windows default input (NX-VOZ-002)
                try:
                    self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=FRAME,
                                                  device=device,
                                                  callback=lambda data, *_: self._frames.put(data[:, 0].copy()))
                except Exception:  # chosen mic unplugged/renamed: fall back to the default one
                    self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=FRAME,
                                                  callback=lambda data, *_: self._frames.put(data[:, 0].copy()))
                self._stream.start()

    def reopen(self):
        """Settings > Microphone changed: restart the capture on the new device if it was open."""
        was_open = self._stream is not None
        self._close()
        if was_open:
            self._open()

    def _close(self):
        with self._lock:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    # -- capture loop ------------------------------------------------------
    def _loop(self):
        det, during, tick = SpeechDetector(), False, 0
        while True:
            frame = self._frames.get()
            if self.mode == "hold":  # key held: keep everything, no voice detection
                self._hold.append(frame)
                tick += 1
                if tick % 2 == 0:
                    self.on_level(round(min(1.0, float(np.sqrt(np.mean(frame ** 2))) / 0.12), 2))
                continue
            if self.mode == "off":
                if det.active:
                    det.reset_segment()
                continue
            during_speech = self.speaker.speaking.is_set() and not self.speaker.paused.is_set()
            if not det.active:
                during = during_speech
                det.max_frames = int((MAX_CONTROL_SECONDS if during else 30) * FRAMES_PER_SECOND)
            event = det.feed(frame)
            if event == "start":
                self.seg_start = time.time()  # v0.18.1: when this utterance began (echo check)
            if event in ("start", "speech") and not during_speech:
                tick += 1
                if tick % 2 == 0:  # ~16 updates per second for the UI ring
                    rms = float(np.sqrt(np.mean(frame ** 2)))
                    self.on_level(round(min(1.0, rms / 0.12), 2))
            if event == "end":
                audio = det.audio
                self.on_level(0)
                too_long = during and len(audio) >= MAX_CONTROL_SECONDS * RATE
                if len(audio) > RATE * 0.4 and not too_long:
                    self._handle(audio, during)

    @staticmethod
    def stt_language():
        """Whisper guesses the language badly on short phrases: use the chosen one, else the app's."""
        return settings["language"] if settings["language"] in LANGS else lang()

    def _handle(self, audio, during_speech, held=False):
        if not self.ready:
            return
        was_ptt = held or self.mode == "ptt"
        if was_ptt and not held:  # one utterance captured: go back to live listening or release the mic
            self.mode = "live" if self.live else "off"
            if not self.live:
                self._close()
        if not during_speech:
            self.on_state("transcribing")
        from .db import db

        try:
            name = ((db.get_profile() or {}).get("name") or "").split()[0]
        except Exception:
            name = ""
        segments, _ = self.model.transcribe(
            normalize_audio(audio), language=self.stt_language(),
            beam_size=1 if during_speech else max(1, int(settings["stt_beam"])),
            vad_filter=False, condition_on_previous_text=False, initial_prompt=initial_prompt(name))
        # drop segments Whisper itself flags as non-speech (hallucinations on noise: "Obrigado.", "Legendas...").
        # v0.18.1: while listening by itself (not push-to-talk) also low-confidence and repetitive segments
        if was_ptt:
            kept = [s for s in segments if s.no_speech_prob < 0.6 or s.avg_logprob > -0.6]
        else:
            kept = [s for s in segments if (s.no_speech_prob < 0.6 or s.avg_logprob > -0.6)
                    and s.avg_logprob > -1.1 and getattr(s, "compression_ratio", 1.0) < 2.4]
        text = " ".join(s.text for s in kept).strip()
        if text and not was_ptt:
            if is_hallucination(text):
                self.dropped.append(("noise", text))
                text = ""
            elif not during_speech and is_echo(text, self.speaker.recent_speech(),
                                               right_after=self.seg_start - self.speaker.ended_at < ECHO_TAIL):
                self.dropped.append(("echo", text))
                text = ""
            del self.dropped[:-20]
        if not during_speech:
            self.on_state("standby" if self.mode == "live" else "idle")
        if not text:
            return
        if was_ptt or during_speech or not self.wake_required():
            self.on_text(text, during_speech)
            return
        self._wake_check(text)

    # v0.14/v0.15 measured (CHANGELOG v0.15.0): pre-checking "Nexus" with a smaller Whisper doesn't pay off. With the
    # same model it saves nothing (fixed 30 s encoder window); with "tiny" it is 4-7x cheaper but misses the wake
    # word (8/8 in digital silence, 7/8 at 43 dB SNR, 2/8 with a fan). A missed command is worse than CPU time, so
    # every utterance gets the full model; real savings need a dedicated keyword spotter (future).

    def _wake_check(self, text):
        m = WAKE_RE.search(text)
        if m:
            command = text[m.end():].strip()
            if len(command) > 2:
                self.on_text(command, False)
            else:
                self.awake_until = time.time() + 8
                self.on_state("awake")
        elif time.time() < self.awake_until:
            self.awake_until = 0
            self.on_text(text, False)
