"""LLM client. Talks to Ollama through its native API (larger context window, model kept warm)
and to any other OpenAI-compatible server (LM Studio, llama.cpp server) through /chat/completions."""
import json
import re

import httpx

from .config import settings

TIMEOUT = httpx.Timeout(300, connect=5)
last_stats: dict = {}  # token counts/timing of the last call, for diagnostics
calls_log: list = []   # every call's stats (benchmarks read and clear it)


class LLMOffline(Exception):
    pass


def _headers():
    return {"Authorization": f"Bearer {settings['llm_api_key']}"}


def _base():
    # On Windows "localhost" resolves to IPv6 ::1 first; Ollama listens on IPv4 only, so every request waited ~2 s
    # for the IPv6 attempt to time out (measured 2.08 s vs 0.008 s). Always use the IPv4 loopback.
    return re.sub(r"//localhost(?=[:/]|$)", "//127.0.0.1", settings["llm_base_url"].rstrip("/"))


def _is_ollama() -> bool:
    provider = settings["llm_provider"]
    return provider == "ollama" or (provider == "auto" and ":11434" in _base())


def _ollama_root():
    return re.sub(r"/v1$", "", _base())


def status() -> dict:
    """Is the server reachable and is the configured model available?"""
    try:
        r = httpx.get(f"{_base()}/models", headers=_headers(), timeout=3)
        r.raise_for_status()
        models = [m["id"] for m in r.json().get("data", [])]
    except Exception as exc:
        return {"online": False, "model": settings["llm_model"], "models": [], "error": str(exc)}
    wanted = settings["llm_model"]
    ready = wanted in models or f"{wanted}:latest" in models
    return {"online": True, "model": wanted, "model_ready": ready, "models": models}


def stream_chat(messages: list, tools: list | None = None, temperature: float | None = None):
    """Yield ("token", text) while streaming and finally ("tool_calls", [...]) or ("done", None).

    `messages` use the OpenAI shape (tool call arguments as JSON strings); tool calls come back as
    {"id", "name", "arguments": <json string>} whichever backend is used."""
    temperature = settings["llm_temperature"] if temperature is None else temperature
    stream = _stream_ollama if _is_ollama() else _stream_openai
    try:
        yield from stream(messages, tools, temperature)
    except httpx.HTTPError as exc:
        raise LLMOffline(str(exc)) from exc


# While the app is open the model stays in VRAM (reloading costs ~7 s + re-processing the prompt ~20 s);
# unload() releases it when the window closes. 2 h is a safety net if the app crashes.
KEEP_ALIVE = "2h"


def _native_body(messages, tools, temperature, stream=True, **options):
    native = []
    for m in messages:
        m = dict(m)
        if m.get("tool_calls"):
            m["tool_calls"] = [{"function": {"name": c["function"]["name"],
                                             "arguments": json.loads(c["function"]["arguments"] or "{}")}}
                               for c in m["tool_calls"]]
        if m["role"] == "tool":
            m = {"role": "tool", "content": m["content"], "tool_name": m.get("name", "")}
        native.append(m)
    body = {
        "model": settings["llm_model"],
        "messages": native,
        "stream": stream,
        "keep_alive": KEEP_ALIVE,
        "think": False,  # reasoning models (qwen3, deepseek-r1) answer directly: much faster for an assistant
        "options": {"temperature": temperature, "num_ctx": settings["llm_context"], **options},
    }
    if tools:
        body["tools"] = tools
    return body


def prefill(messages: list, tools: list | None = None) -> dict:
    """Load the model and process the fixed part of the prompt (rules, profile, tools) without answering, so the
    user's first message only pays for its own tokens. Ollama keeps the processed prefix in its KV cache."""
    if not _is_ollama():
        return {"skipped": "not ollama"}
    body = _native_body(messages, tools, settings["llm_temperature"], stream=False, num_predict=1)
    r = httpx.post(f"{_ollama_root()}/api/chat", json=body, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return {k: data.get(k) for k in ("load_duration", "prompt_eval_count", "prompt_eval_duration", "total_duration")}


def unload():
    """Free the GPU memory when NEXUS closes (games and other apps get the VRAM back)."""
    if _is_ollama():
        try:
            httpx.post(f"{_ollama_root()}/api/generate", json={"model": settings["llm_model"], "keep_alive": 0}, timeout=10)
        except httpx.HTTPError:
            pass


def _stream_ollama(messages, tools, temperature):
    body = _native_body(messages, tools, temperature)
    calls = []
    with httpx.stream("POST", f"{_ollama_root()}/api/chat", json=body, timeout=TIMEOUT) as r:
        if r.status_code >= 400:
            r.read()
            raise LLMOffline(f"HTTP {r.status_code}: {r.text[:300]}")
        for line in r.iter_lines():
            if not line.strip():
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise LLMOffline(chunk["error"])
            msg = chunk.get("message") or {}
            if msg.get("content"):
                yield "token", msg["content"]
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args = fn.get("arguments") or {}
                calls.append({"id": tc.get("id", ""), "name": fn.get("name", ""),
                              "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)})
            if chunk.get("done"):
                last_stats.clear()
                last_stats.update({k: chunk.get(k) for k in ("prompt_eval_count", "prompt_eval_duration", "eval_count",
                                                              "eval_duration", "load_duration", "total_duration")})
                calls_log.append(dict(last_stats))
    yield ("tool_calls", calls) if calls else ("done", None)


def _stream_openai(messages, tools, temperature):
    body = {"model": settings["llm_model"], "messages": messages, "stream": True, "temperature": temperature}
    if tools:
        body["tools"] = tools
    calls: dict[int, dict] = {}
    with httpx.stream("POST", f"{_base()}/chat/completions", json=body, headers=_headers(), timeout=TIMEOUT) as r:
        if r.status_code >= 400:
            r.read()
            raise LLMOffline(f"HTTP {r.status_code}: {r.text[:300]}")
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            if not chunk.get("choices"):
                continue
            delta = chunk["choices"][0].get("delta") or {}
            if delta.get("content"):
                yield "token", delta["content"]
            for tc in delta.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", len(calls)), {"id": "", "name": "", "arguments": ""})
                slot["id"] = tc.get("id") or slot["id"]
                fn = tc.get("function") or {}
                slot["name"] += fn.get("name") or ""
                slot["arguments"] += fn.get("arguments") or ""
    yield ("tool_calls", [calls[i] for i in sorted(calls)]) if calls else ("done", None)


def complete(messages: list, temperature: float = 0.2) -> str:
    """Non-streaming helper for background jobs (memory extraction)."""
    return "".join(text for kind, text in stream_chat(messages, temperature=temperature) if kind == "token")
