"""Offline voice: faster-whisper speech-to-text + Windows SAPI text-to-speech with effects (tts.py)."""
import queue
import re
import threading
import time

import numpy as np

from .config import settings
from .i18n import LANGS, detect, lang

RATE = 16000
FRAME = 480  # 30 ms
WAKE_RE = re.compile(r"\b(n[eé]?[xk]+[ uo]*[sz]|nexos|nexo|next us|nex us|néxus)\b[\s,.!?:;-]*", re.IGNORECASE)
ENV_STEP = 0.04  # seconds per point of the speech envelope sent to the UI ring
MAX_CONTROL_SECONDS = 4  # while NEXUS speaks, only short utterances ("pausa", "stop") are considered


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
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
    def say(self, text: str, force: bool = False, remember: bool = True):
        """Queue text. The voice follows the text's language (pt/en/es), else the app language."""
        text = clean_for_speech(text)
        if not text or not (speech_allowed() or force):
            return
        if remember:
            self.last_text = text
        self.interrupt.clear()
        self.q.put(text)

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
            text = self.q.get()
            voice, pitch = engine.pick(detect(text) or lang(), settings["voice_gender"])
            self.speaking.set()
            self.on_state("speaking")
            sentences, i = tts.split_sentences(text), 0
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


class Listener:
    """Microphone capture with an energy VAD; transcribes each utterance with Whisper.

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

                self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=FRAME,
                                              callback=lambda data, *_: self._frames.put(data[:, 0].copy()))
                self._stream.start()

    def _close(self):
        with self._lock:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    # -- capture loop ------------------------------------------------------
    def _loop(self):
        floor, voiced, silence, buf, pre, tick = 0.003, 0, 0, [], [], 0
        while True:
            frame = self._frames.get()
            if self.mode == "off":
                buf, voiced, silence = [], 0, 0
                continue
            during_speech = self.speaker.speaking.is_set() and not self.speaker.paused.is_set()
            rms = float(np.sqrt(np.mean(frame ** 2)))
            threshold = max(floor * 3.0, 0.008)
            speech = rms > threshold
            if not buf:
                floor = 0.95 * floor + 0.05 * rms if not speech else floor
                pre = (pre + [frame])[-10:]  # 300 ms pre-roll
                voiced = voiced + 1 if speech else 0
                if voiced >= 3:
                    buf, silence = list(pre), 0
                continue
            buf.append(frame)
            if not during_speech:
                tick += 1
                if tick % 2 == 0:  # ~16 updates per second for the UI ring
                    self.on_level(round(min(1.0, rms / 0.12), 2))
            silence = 0 if speech else silence + 1
            limit = MAX_CONTROL_SECONDS * 33 if during_speech else 30 * 33
            if silence > 25 or len(buf) > limit:  # ~750 ms of silence or length limit
                audio = np.concatenate(buf)
                buf, voiced, pre = [], 0, []
                self.on_level(0)
                too_long = during_speech and len(audio) >= MAX_CONTROL_SECONDS * RATE
                if len(audio) > RATE * 0.4 and not too_long:
                    self._handle(audio, during_speech)

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
        language = settings["language"] if settings["language"] in LANGS else None
        segments, _ = self.model.transcribe(audio, language=language, beam_size=1, vad_filter=False,
                                            condition_on_previous_text=False)
        text = " ".join(s.text for s in segments).strip()
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
