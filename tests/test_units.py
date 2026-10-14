"""Fast checks that need no AI server.   Run:  .venv\\Scripts\\python tests\\test_units.py"""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

from datetime import datetime, timedelta

import numpy as np

from nexus import assistant, control, knowledge, memory, tts
from nexus.db import db

failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name + (f"  ({detail})" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# -- conversation control detector (PT/EN/ES, with false-positive traps) --------------------------------
CASES = [
    ("Pausa", "pause"), ("Nexus, segura um pouquinho aí que eu vou atender a porta", "pause"),
    ("hold on, someone is at the door", "pause"), ("Espera un momento que me llaman", "pause"),
    ("pode continuar", "resume"), ("Repete por favor", "repeat"), ("O que você disse?", "repeat"),
    ("Não entendi", "clearer"), ("I didn't understand", "clearer"), ("Para de falar", "stop"), ("Para!", "stop"),
    ("para quem é a reunião de amanhã?", None), ("Continue a lista de compras com leite e pão", None),
    ("Um momento histórico foi a queda do muro de Berlim", None), ("Paraná fica no sul do Brasil", None),
    ("fale os valores exatos", None), ("E de uma mulher?", None),
]
for text, expected in CASES:
    got = control.detect(text)
    check(f"control.detect({text!r}) == {expected}", got == expected, f"got {got}")

# -- session-scoped history and action log (NX-LLM-019) -------------------------------------------------
old = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
db.execute("INSERT INTO messages(role, content, ts) VALUES ('user', 'Registra que gastei 42 reais', ?)", (old,))
db.execute("INSERT INTO actions(ts, kind, summary) VALUES (?, 'dados', 'Registrou em gastos: 42')", (old,))
memory.add_message("user", "Quanto pesa o coração em um homem adulto?")
memory.add_message("assistant", "Em média, cerca de 280 a 340 g.")
hist = memory.history(12)
check("history excludes previous sessions", all("gastei" not in m["content"] for m in hist), str(hist))
check("history keeps the current session", len(hist) == 2, str(hist))
context = assistant.build_context("fale os valores exatos")
check("context has no old action log", "gastos" not in context)

# -- knowledge: anatomy book and follow-up anchoring --------------------------------------------------------
knowledge.load_seed()
check("anatomy book indexed", any(d["category"] == "Anatomia" for d in knowledge.documents()))
check("follow-up 'E de uma mulher?' pulls the heart section",
      "Coração" in assistant.build_context("E de uma mulher?"))

# -- voice effect: no electrolarynx buzz, close to the dry voice (NX-VOZ-015) -----------------------------
t = np.arange(int(tts.RATE * 1.5)) / tts.RATE
dry = (0.3 * np.sin(2 * np.pi * 140 * t) * (1 + np.sin(2 * np.pi * 4 * t)) / 2).astype(np.float32)
wet = tts.apply_effect(dry, "jarvis")[: len(dry)]
fidelity = float(np.corrcoef(dry, wet)[0, 1])
f = np.fft.rfftfreq(len(dry), 1 / tts.RATE)


def buzz(sig):  # amplitude-modulation energy at 45 Hz, relative to the envelope's low-frequency energy
    s = np.abs(np.fft.rfft(sig * sig))
    return s[(f > 43) & (f < 47)].max() / s[(f > 1) & (f < 400)].mean()


ring_modulated = dry * (0.8 + 0.2 * np.sin(2 * np.pi * 45 * t))  # what the old v0.2/v0.3 effect did
check("jarvis effect keeps the voice (fidelity > 0.9)", fidelity > 0.9, f"{fidelity:.2f}")
check("jarvis effect has far less 45 Hz buzz than the old ring modulation",
      buzz(wet) < buzz(ring_modulated) / 10, f"new {buzz(wet):.3f} vs old {buzz(ring_modulated):.3f}")

# -- spoken name: NÉCSUS / NÉ-QUI-SÚS (NX-VOZ-016) ---------------------------------------------------------
check("name spoken as Nécsus in Portuguese", tts.pronounce("Eu sou NEXUS. N.E.X.U.S online.", "pt") == "Eu sou Nécsus. Nécsus online.")
check("name untouched in English", tts.pronounce("I am NEXUS.", "en") == "I am Nexus.")
check("other words untouched", tts.pronounce("nexusAI e annexus", "pt") == "nexusAI e annexus")

print(f"\n{len(failures)} failure(s)")
raise SystemExit(1 if failures else 0)
