# N.E.X.U.S

**Networked Experiential Intelligence & User System** — a personal AI assistant for Windows that runs **100% on your
own computer**, on an **AMD Radeon** graphics card. It remembers you, manages your schedule, tasks and data, talks and
listens, looks things up online when you ask, and changes its own interface when you tell it to. No cloud account, no
telemetry, no API keys.

> Português: [README.pt-BR.md](README.pt-BR.md) · Changelog (PT): [CHANGELOG.md](CHANGELOG.md) ·
> Known issues: [errors.txt](errors.txt) ([PT](erros.txt) · [ES](errores.txt))

Built for the **AMD Developer Hackathon: ACT III** (lablab.ai). Version **1.0.0** · MIT License (see
[Authorship](#license-and-authorship)).

## Quick start

1. Download **`NEXUS-Setup-1.0.0.exe`** from the [latest release](https://github.com/Bryan-M-Almeida/nexusAI/releases/latest)
   and run it (no administrator needed).
2. The installer (English, Portuguese or Spanish) asks a few things and sets NEXUS up for you:
   - your **profile JSON** (optional) — NEXUS opens already knowing your name and interests;
   - the **AI model for your graphics card** — it detects the card and its memory and recommends one;
   - **look and voice** — ring or PET, colour theme, male or female voice;
   - **Ollama**, the local AI engine — downloaded and installed if it's missing;
   - desktop shortcut and *open with Windows*.
3. Open NEXUS. While a short **spoken tutorial** plays, it loads the AI and the voice in the background. Then just
   say **"Nexus"** and your request, hold **Ctrl+Space**, or type.

Updates: *Settings → Updates* downloads only what changed (~18 MB), not the whole installer.

## Where AMD comes in

| | |
|---|---|
| **AI on the Radeon GPU** | The language model runs locally through Ollama on the AMD card (**Vulkan** backend). Reference PC: Radeon RX 6600 XT 8 GB — NEX-1.0 (Qwen3 8B) at ~21–35 tokens/s, 92–100% on the GPU, ~5 s per answer on average. |
| **AMD panel** | *Settings → AMD*: card, driver and Adrenalin version (from the Windows registry), live GPU use and VRAM (Windows performance counters), the model loaded on the card, free VRAM / warm-up buttons, and a Vulkan vs ROCm comparison. |
| **Model for each card** | The NEX-1.0 family (Lite 1.7B · Mini 4B · NEX-1.0 8B · Pro 14B · Max 30B-A3B) is matched to the VRAM: the largest model that runs (almost) entirely on the card is recommended, both in the installer and in the app. |
| **ROCm and NPU (beta)** | NEXUS reads the chip list shipped with Ollama and offers ROCm only where it works (gfx906/1030/110x/115x/120x); on gfx1032 it keeps Vulkan (forced ROCm measured 9.1 vs 35.6 tok/s). Ryzen AI NPUs are reached through AMD **Lemonade Server** (one click, beta). |
| **Games first** (beta) | Opening a game from NEXUS suspends it and frees the VRAM; it comes back when you say "Nexus" or return to it. |

## What it does

| Feature | How |
|---|---|
| Conversation | Text and voice in **English, Portuguese and Spanish**; follow-up questions keep the context ("and 50 of those in euros?", "what time is it there?"). |
| Voice | Offline speech recognition (Whisper, bundled) with echo protection; offline speech with the Windows voices, male or female, optional effects. |
| Memory | Profile, facts about you, conversations with search, and a log of every action. |
| Actions | Tasks, schedule, reminders (spoken and on screen), notes and free data collections (expenses, workouts, readings…) — always through real tool calls, checked by safety nets. |
| Knowledge | Built-in books (first aid, philosophy, finance, programming, health, productivity) plus anything you teach it or drop in the `inbox` folder; local full-text search. |
| Live data | Weather, currency, crypto, world clock, translation, holidays, air quality, news, calculator, units, Wikipedia — routed without the AI and cached, so simple questions answer in under a second. Facts about songs, books and people are looked up instead of guessed. |
| Interface | A clean screen with the NEXUS ring (or the PET orb whose eye follows the mouse); menus hide at the screen edges; F1 shows every shortcut. Ask "open settings" or "make the ring red" and it does it. |
| Accounts | Local accounts with a password, and a guest mode that leaves nothing behind. |
| Safety | Emergency mode answers first-aid situations instantly from the manual and tells you to call emergency services; nothing leaves the PC unless you use an online integration. |
| Beta | Workspace (the AI edits files in an isolated folder), library and podcast mode, browser and music, lyrics from a source you name, media and app control, training mode, memory import from other assistants, custom integrations, ROCm/NPU. Off in *user mode*, on in *developer mode*. |

*Settings → About* lists exactly what works, what is in beta and what doesn't work yet; *Settings → Possible errors*
lists the known issues with their fixes.

## Requirements

Measured on the reference PC (Ryzen 5 5600G, 16 GB RAM, Radeon RX 6600 XT 8 GB).

| | Minimum | Recommended |
|---|---|---|
| System | Windows 10/11 64-bit | Windows 11 64-bit |
| RAM | 8 GB (NEX-1.0 Lite) | 16 GB |
| Graphics | none (runs on the processor, slow) | 8 GB VRAM (e.g. Radeon RX 6600 XT) |
| Disk | ~5 GB | ~12 GB on an SSD |

Disk: NEXUS ~0.75 GB (voice included), Ollama ~2.8 GB, model 1.4–9.3 GB depending on the card.

| Model (RX 6600 XT 8 GB) | On the GPU | Tokens/s | Average answer | Conversation eval |
|---|---|---|---|---|
| NEX-1.0 Lite (qwen3:1.7b) | 100% | 30.2 | 2.8 s | 32/37 |
| NEX-1.0 Mini (qwen3:4b-instruct) | 100% | 24.2 | 6.6 s | 36/37 |
| **NEX-1.0 (qwen3:8b)** — default | 92% | 21.4 | 5.5 s | 37/37 |
| NEX-1.0 Pro (qwen3:14b) | 58% | 7.3 | 12.9 s | 37/37 |

## Run from source

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1     # Python venv + dependencies
winget install Ollama.Ollama; ollama pull qwen3:8b
.\.venv\Scripts\python run_nexus.py
```

`NEXUS_DEBUG=1` opens the DevTools; `NEXUS_HOME=<folder>` uses another data folder. Open
`nexus/web/index.html?mock` in a browser to work on the interface without Python.

AMD tip: if Ollama's `server.log` says "AMD driver is too old" it is on Vulkan; setting `OLLAMA_FLASH_ATTENTION=0`
made prompt reading ~3.5x faster on the RX 6600 XT (NEXUS can set it for you in *Settings → Performance*).

## Tests

Tests always use a temporary data folder.

```powershell
.\.venv\Scripts\python tests\test_units.py          # ~350 checks, seconds, no AI
.\.venv\Scripts\python tests\conversation_eval.py   # 37 checks with the real model
.\.venv\Scripts\python tests\bench_models.py        # every NEX-1.0 model on this PC
```

## Build

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1      # dist\NEXUS\NEXUS.exe
powershell -ExecutionPolicy Bypass -File release.ps1    # + installer and small update in dist\release
dist\NEXUS\NEXUS.exe --selftest                        # headless check, writes selftest.json
```

The installer needs Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

## Data

Installed: program in `%LOCALAPPDATA%\Programs\NEXUS`, your data in `%LOCALAPPDATA%\NEXUS` (`nexus.db`, `settings.json`,
`inbox/`, daily backups). From source: `./data`. Uninstalling asks before deleting your data.

## License and authorship

Created by **Bryan Maciel de Almeida**. © 2026.

The **code** is free software under the [MIT License](LICENSE). The **name and visual identity are not licensed**
(see [NOTICE](NOTICE)): the "N.E.X.U.S" / "NEXUS" name, the NEX-1.0 model names, the logo, the icon, the PET and the
ring/HUD visual identity belong to the author. Modified or redistributed versions must use another name and their own
artwork; saying "based on N.E.X.U.S" is fine.

Third-party components keep their own licenses: pywebview (BSD-3), faster-whisper and CTranslate2 (MIT), ONNX Runtime
(MIT), httpx / NumPy / pypdf / PyAV (BSD-3), sounddevice / comtypes (MIT), Hugging Face Hub / tokenizers (Apache-2.0),
Ollama (MIT, installed separately), Qwen3 models (Apache-2.0), Whisper models (MIT), fonts (SIL OFL 1.1), PyInstaller
(GPL-2.0 with the bootloader exception, build only), Inno Setup (Inno Setup License, build only).
