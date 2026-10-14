"""Offline voice: faster-whisper speech-to-text + Windows SAPI text-to-speech with effects (tts.py)."""
import queue
import re
import threading
import time

import numpy as np

from .config import settings
from .i18n import LANGS, detect, lang

RATE = 16000
FRAME = 512  # 32 ms: the window Silero VAD expects at 16 kHz
FRAMES_PER_SECOND = RATE / FRAME
# "Nexus" as Whisper tends to write it in pt/en/es: nexus, néxus, nécsus, neksus, nexos, nexis, next us, nex us...
WAKE_RE = re.compile(r"\b(n[eéêiy]?[xk]+s?[ iuoe]*[sz]|n[eé]c?k?s[uo]s|nexo|next? us|nex us|nek us)\b[\s,.!?:;-]*",
                     re.IGNORECASE)
ENV_STEP = 0.04  # seconds per point of the speech envelope sent to the UI ring
MAX_CONTROL_SECONDS = 4  # while NEXUS speaks, only short utterances ("pausa", "stop") are considered


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", " ", text)  # inline code / file paths are shown, not read aloud
    text = re.sub(r"[*_`#>|]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


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
        self.voices: list[dict] = []
        self.error: str | None = None
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True, name="tts").start()

    # -- control -------------------------------------------------------------
    def say(self, text: str, force: bool = False, remember: bool = True, lang_code: str | None = None):
        """Queue text. The voice follows the text's language (pt/en/es), else the app language."""
        text = clean_for_speech(text)
        if not text or not (speech_allowed() or force):
            return
        if remember:
            self.last_text = text
        self.interrupt.clear()
        self.q.put((text, lang_code))

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
            text, code = self.q.get()
            code = code or detect(text) or lang()  # streamed chunks carry the reply language: no voice flips
            voice, pitch = engine.pick(code, settings["voice_gender"])
            self.speaking.set()
            self.on_state("speaking")
            spoken = tts.pronounce(text, code, voice.gender if voice else "male")
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
                    audio = tts.apply_effect(engine.render(sentences[i], voice, pitch, settings["tts_speed"]),
                                             settings["voice_effect"])
                    audio = audio * (max(0, min(100, int(settings["tts_volume"]))) / 100)  # Settings > Voice volume
                    self.on_audio({"env": self._envelope(audio, tts.RATE), "dt": ENV_STEP})
                    sd.play(audio, tts.RATE)
                    sd.wait()
                    if not self.paused.is_set():
                        i += 1
            except Exception as exc:
                self.error = str(exc)
            if self.q.empty():
                time.sleep(0.25)  # let the room echo die before the mic goes back to full listening
                self.speaking.clear()
                self.on_state("idle")


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

    def __init__(self, on_text, on_state, speaker: Speaker, on_level=lambda level: None):
        self.on_text, self.on_state, self.speaker, self.on_level = on_text, on_state, speaker, on_level
        self.model = None
        self.model_error = None
        self.model_state = "loading"  # loading | ready | missing (not downloaded yet) | error
        self.mode = "off"
        self.live = False  # continuous listening wanted (audio mode with mic unmuted)
        self.awake_until = 0.0
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

            self.model = WhisperModel(settings["stt_model"], device="cpu", compute_type="int8",
                                      local_files_only=not download)
            self.model_state = "ready"
            if self.live:  # audio mode was waiting for the model
                self.set_live(True)
        except Exception as exc:
            self.model = None
            self.model_state = "error" if download else "missing"
            self.model_error = str(exc) if download else None

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
            if self.mode == "off":
                if det.active:
                    det.reset_segment()
                continue
            during_speech = self.speaker.speaking.is_set() and not self.speaker.paused.is_set()
            if not det.active:
                during = during_speech
                det.max_frames = int((MAX_CONTROL_SECONDS if during else 30) * FRAMES_PER_SECOND)
            event = det.feed(frame)
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

    def _handle(self, audio, during_speech):
        if not self.ready:
            return
        was_ptt = self.mode == "ptt"
        if was_ptt:  # one utterance captured: go back to live listening or release the mic
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
            normalize_audio(audio), language=self.stt_language(), beam_size=1 if during_speech else 5,
            vad_filter=False, condition_on_previous_text=False, initial_prompt=initial_prompt(name))
        # drop segments Whisper itself flags as non-speech (hallucinations on noise: "Obrigado.", "Legendas...")
        text = " ".join(s.text for s in segments if s.no_speech_prob < 0.6 or s.avg_logprob > -0.6).strip()
        if not during_speech:
            self.on_state("standby" if self.mode == "live" else "idle")
        if not text:
            return
        if was_ptt or during_speech or not settings["require_wake_word"]:
            self.on_text(text, during_speech)
            return
        self._wake_check(text)

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
