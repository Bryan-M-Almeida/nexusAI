"""Voice bench: end-of-speech detection and recognition accuracy, old vs new pipeline.
Synthetic speech (Windows voices) + realistic background noise; relative comparison, not a human-voice score.
Run: .venv\\Scripts\\python tests\\bench_voice.py"""
import _isolated  # noqa: F401

import re
import sys
import time
import unicodedata

import numpy as np

from nexus import tts, voice

SR = 16000
PHRASES = [
    "Nexus, que horas são agora?", "Me lembra de ligar para o dentista amanhã às dez horas.",
    "Registra que gastei quarenta e dois reais no mercado.", "Qual é a capital da Austrália?",
    "Nexus, vai chover hoje em São Paulo?", "Eu tenho dois gatos chamados Pixel e Byte.", "Pausa.",
    "Não entendi, explica melhor.", "Quanto pesa o coração de um homem adulto?",
    "Nexus, agenda uma reunião com o time na sexta-feira.",
]
rng = np.random.default_rng(7)


def to16k(x):
    n = int(len(x) * SR / tts.RATE)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def noise(n, level):
    brown = np.cumsum(rng.standard_normal(n)); brown -= np.convolve(brown, np.ones(400) / 400, "same")  # fan rumble
    white = rng.standard_normal(n) * 0.35
    x = brown / (np.abs(brown).max() + 1e-9) + white / 3
    return (x / np.sqrt(np.mean(x ** 2)) * level).astype(np.float32)


def norm_words(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", t)


def wer(ref, hyp):
    r, h = norm_words(ref), norm_words(hyp)
    d = np.arange(len(h) + 1)
    for i in range(1, len(r) + 1):
        prev, d[0] = d.copy(), i
        for j in range(1, len(h) + 1):
            d[j] = min(prev[j] + 1, d[j - 1] + 1, prev[j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(len(r), 1)


engine = tts.Engine()
voices = {v.name: v for v in engine.voices}
clips = []
for vname in ("Microsoft Maria", "Microsoft Daniel"):
    for p in PHRASES:
        speech = to16k(engine.render(p, voices[vname], 0))
        speech = speech / np.abs(speech).max() * 0.3  # moderate mic level
        clips.append((vname, p, speech))

# ---------------------------------------------------------------- 1) end of speech (endpointing)
def energy_endpoint(stream):
    """Replica of the v0.7 loop: returns seconds after speech end when the segment closes (None = never)."""
    floor, voiced, silence, buf, frames = 0.003, 0, 0, None, 0
    for i in range(0, len(stream) - 480, 480):
        f = stream[i:i + 480]; frames += 1
        rms = float(np.sqrt(np.mean(f ** 2))); speech = rms > max(floor * 3.0, 0.008)
        if buf is None:
            floor = 0.95 * floor + 0.05 * rms if not speech else floor
            voiced = voiced + 1 if speech else 0
            if voiced >= 3:
                buf, silence = 0, 0
            continue
        buf += 1; silence = 0 if speech else silence + 1
        if silence > 25 or buf > 30 * 33:
            return (i + 480) / SR
    return None


def silero_endpoint(stream):
    det = voice.SpeechDetector()
    for i in range(0, len(stream) - 512, 512):
        if det.feed(stream[i:i + 512]) == "end":
            return (i + 512) / SR
    return None


print("1) FIM DA GRAVAÇÃO — fala de ~2 s seguida de 4 s de ruído de fundo")
for level, label in ((0.004, "ruído baixo"), (0.012, "ruído médio (ventilador)"), (0.025, "ruído alto")):
    res = {"energia (v0.7)": [], "Silero (v0.8)": []}
    for _, _, speech in clips[:6]:
        pre, post = noise(SR, level), noise(4 * SR, level)
        stream = np.concatenate([pre, speech + noise(len(speech), level), post])
        speech_end = (len(pre) + len(speech)) / SR
        for name, fn in (("energia (v0.7)", energy_endpoint), ("Silero (v0.8)", silero_endpoint)):
            t = fn(stream)
            res[name].append(None if t is None else t - speech_end)
    for name, vals in res.items():
        closed = [v for v in vals if v is not None]
        print(f"   {label:<26} {name:<15}: encerrou {len(closed)}/{len(vals)}"
              + (f", em média {np.mean(closed):.2f}s após o fim da fala" if closed else " (gravação nunca termina)"))

# ---------------------------------------------------------------- 2) recognition
if "--skip-asr" in sys.argv:
    raise SystemExit
from faster_whisper import WhisperModel  # noqa: E402

model = WhisperModel("small", device="cpu", compute_type="int8")
CONFIGS = {
    "v0.7 (idioma auto, beam 1)": dict(language=None, beam_size=1),
    "v0.8 (pt, beam 5, vocabulário)": dict(language="pt", beam_size=5, initial_prompt=voice.initial_prompt("Bryan")),
}
print("\n2) RECONHECIMENTO — 20 frases (Maria e Daniel) com ruído médio")
for name, cfg in CONFIGS.items():
    errs, wake_hits, wake_total, secs = [], 0, 0, 0.0
    for vname, phrase, speech in clips:
        audio = speech + noise(len(speech), 0.012)
        if name.startswith("v0.8"):
            audio = voice.normalize_audio(audio)
        t0 = time.time()
        segs, _ = model.transcribe(audio, vad_filter=False, condition_on_previous_text=False, **cfg)
        text = " ".join(s.text for s in segs).strip()
        secs += time.time() - t0
        errs.append(wer(phrase, text))
        if phrase.startswith("Nexus"):
            wake_total += 1
            wake_hits += bool(voice.WAKE_RE.search(text))
        if "-v" in sys.argv:
            print(f"      [{vname.split()[1]}] {phrase!r} -> {text!r}")
    print(f"   {name:<32}: erro de palavras (WER) {np.mean(errs) * 100:5.1f}% | 'Nexus' reconhecido "
          f"{wake_hits}/{wake_total} | {secs / len(clips):.2f}s por frase")
