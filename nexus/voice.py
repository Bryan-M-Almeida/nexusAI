"""Offline voice: faster-whisper speech-to-text + Windows SAPI text-to-speech (pyttsx3)."""
import queue
import re
import threading
import time

import numpy as np

from .config import settings
from .i18n import lang

RATE = 16000
FRAME = 480  # 30 ms
WAKE_RE = re.compile(r"\b(n[eé]?[xk]+[ uo]*[sz]|nexos|nexo|next us|nex us|néxus)\b[\s,.!?:;-]*", re.IGNORECASE)
VOICE_HINTS = {"pt": ("portugu", "brazil", "maria"), "en": ("english", "zira", "david"), "es": ("spanish", "españ", "helena", "sabina", "laura")}


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[*_`#>|]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


class Speaker:
    """Speaks sentence by sentence on its own thread so it can be interrupted."""

    def __init__(self, on_state):
        self.on_state = on_state
        self.q: queue.Queue = queue.Queue()
        self.speaking = threading.Event()
        self.interrupt = threading.Event()
        threading.Thread(target=self._run, daemon=True, name="tts").start()

    def say(self, text: str):
        text = clean_for_speech(text)
        if text and settings["voice_enabled"]:
            self.interrupt.clear()
            self.q.put(text)

    def stop(self):
        self.interrupt.set()
        while not self.q.empty():
            self.q.get_nowait()

    def _pick_voice(self, engine):
        hints = VOICE_HINTS[lang()]
        for v in engine.getProperty("voices"):
            if any(h in v.name.lower() for h in hints):
                return v.id
        return None

    def _run(self):
        import pyttsx3

        engine = pyttsx3.init()
        while True:
            text = self.q.get()
            if voice_id := self._pick_voice(engine):
                engine.setProperty("voice", voice_id)
            engine.setProperty("rate", settings["tts_rate"])
            self.speaking.set()
            self.on_state("speaking")
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if self.interrupt.is_set():
                    break
                engine.say(sentence)
                engine.runAndWait()
            if self.q.empty():
                time.sleep(0.25)  # let the room echo die before the mic reopens
                self.speaking.clear()
                self.on_state("idle")


class Listener:
    """Microphone capture with an energy VAD; transcribes each utterance with Whisper."""

    def __init__(self, on_text, on_state, speaker: Speaker):
        self.on_text, self.on_state, self.speaker = on_text, on_state, speaker
        self.model = None
        self.model_error = None
        self.model_state = "loading"  # loading | ready | missing (not downloaded yet) | error
        self.mode = "off"  # off | ptt (one utterance) | wake (continuous, needs the wake word)
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

    def set_wake_mode(self, enabled: bool):
        self.mode = "wake" if enabled else "off"
        if enabled:
            self.ensure_model()
            self._open()
            self.on_state("standby")
        else:
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
        floor, voiced, silence, buf, pre = 0.003, 0, 0, [], []
        while True:
            frame = self._frames.get()
            if self.speaker.speaking.is_set() and self.mode == "wake":
                buf, voiced, silence = [], 0, 0  # don't listen to ourselves
                continue
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
            silence = 0 if speech else silence + 1
            if silence > 25 or len(buf) > 30 * 33:  # ~750 ms of silence or 30 s max
                audio = np.concatenate(buf)
                buf, voiced, pre = [], 0, []
                if len(audio) > RATE * 0.4:
                    self._handle(audio)

    def _handle(self, audio):
        if not self.ready:
            return
        was_ptt = self.mode == "ptt"
        if was_ptt:  # one utterance captured: go back to standby or release the mic
            if settings["wake_mode"]:
                self.mode = "wake"
            else:
                self.mode = "off"
                self._close()
        self.on_state("transcribing")
        language = settings["language"] if settings["language"] in VOICE_HINTS else None
        segments, _ = self.model.transcribe(audio, language=language, beam_size=1, vad_filter=False,
                                            condition_on_previous_text=False)
        text = " ".join(s.text for s in segments).strip()
        if was_ptt:
            self.on_state("standby" if self.mode == "wake" else "idle")
            if text:
                self.on_text(text)
            return
        self.on_state("standby")
        self._wake_check(text)

    def _wake_check(self, text):
        if not text:
            return
        m = WAKE_RE.search(text)
        if m:
            command = text[m.end():].strip()
            if len(command) > 2:
                self.on_text(command)
            else:
                self.awake_until = time.time() + 8
                self.on_state("awake")
        elif time.time() < self.awake_until:
            self.awake_until = 0
            self.on_text(text)
