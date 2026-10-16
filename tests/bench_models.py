"""Compare local models on this PC (v0.18.6): load time, how much fits on the graphics card, speed and the quality of
the full conversation eval (the same 37 checks NEXUS is released with).
Run:  .venv\\Scripts\\python tests\\bench_models.py qwen3:1.7b qwen3:4b qwen3:8b qwen3:14b
Writes tests/bench_models.json (read by nexus/models.py as the measured numbers of the reference PC)."""
import _isolated  # noqa: F401  (must be first: isolates the data folder)

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from nexus import assistant, hardware, llm
from nexus.config import settings

HERE = Path(__file__).resolve().parent
models = sys.argv[1:] or ["qwen3:1.7b", "qwen3:4b", "qwen3:8b", "qwen3:14b"]
results = {}
for model in models:
    print(f"\n=== {model} ===", flush=True)
    settings["llm_model"], settings["llm_provider"] = model, "ollama"
    for m in llm.loaded():  # start cold: nothing else on the card
        settings["llm_model"] = m["name"]
        llm.unload()
    settings["llm_model"] = model
    time.sleep(2)
    t0 = time.perf_counter()
    stats = assistant.warm_up()
    cold = time.perf_counter() - t0
    loaded = next((m for m in llm.loaded() if m["name"] == model), {"size_mb": 0, "vram_mb": 0})
    print(f"cold start {cold:.1f} s (load {stats.get('load_duration', 0) / 1e9:.1f} s), {loaded['size_mb']} MB, "
          f"{loaded['vram_mb']} MB on the card", flush=True)
    env = {**os.environ, "NEXUS_EVAL_MODEL": model, "PYTHONIOENCODING": "utf-8"}
    t0 = time.perf_counter()
    out = subprocess.run([sys.executable, str(HERE / "conversation_eval.py")], capture_output=True, text=True, env=env,
                         encoding="utf-8", errors="replace", timeout=3600).stdout
    wall = time.perf_counter() - t0
    times = [float(x) for x in re.findall(r"^  \(([0-9.]+)s\)", out, re.M)]
    passed = re.search(r"(\d+)/(\d+) checks passed", out)
    perf = re.search(r"PERF model=\S+ tok_s=(\S+) first_s=(\S+)", out)
    fails = re.findall(r"^  FAIL (.+?)(?:  \[|$)", out, re.M)
    results[model] = {
        "size_mb": loaded["size_mb"], "vram_mb": loaded["vram_mb"],
        "on_gpu_pct": round(100 * loaded["vram_mb"] / loaded["size_mb"]) if loaded["size_mb"] else 0,
        "cold_start_s": round(cold, 1), "load_s": round(stats.get("load_duration", 0) / 1e9, 1),
        "tok_s": float(perf.group(1)) if perf and perf.group(1) != "None" else None,
        "first_s": float(perf.group(2)) if perf and perf.group(2) != "None" else None,
        "avg_answer_s": round(sum(times[:27]) / max(1, len(times[:27])), 2),
        "checks": f"{passed.group(1)}/{passed.group(2)}" if passed else "?", "fails": fails, "eval_minutes": round(wall / 60, 1),
    }
    print(json.dumps(results[model], ensure_ascii=False), flush=True)

out_file = HERE / "bench_models.json"
previous = json.loads(out_file.read_text("utf-8")).get("models", {}) if out_file.exists() else {}
report = {"pc": hardware.summary(), "date": time.strftime("%Y-%m-%d"), "models": {**previous, **results}}
out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
print("\nmodel        on GPU   cold    tok/s  1st word  avg answer  checks")
for m, r in results.items():
    print(f"{m:12} {r['on_gpu_pct']:>5}%  {r['cold_start_s']:>5}s  {r['tok_s']!s:>6}  {r['first_s']!s:>7}s  {r['avg_answer_s']:>8}s  {r['checks']}")
