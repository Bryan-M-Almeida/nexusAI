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


# Settings > AI provider (v0.10). Every one speaks the OpenAI chat-completions format; Ollama also gets its
# native API. "local" = nothing leaves the computer; cloud providers need an API key and receive the messages.
PRESETS = [
    {"id": "ollama", "name": "Ollama", "url": "http://127.0.0.1:11434/v1", "local": True, "key": False},
    {"id": "lmstudio", "name": "LM Studio", "url": "http://127.0.0.1:1234/v1", "local": True, "key": False},
    {"id": "openai", "name": "OpenAI", "url": "https://api.openai.com/v1", "local": False, "key": True},
    {"id": "anthropic", "name": "Anthropic (Claude)", "url": "https://api.anthropic.com/v1", "local": False, "key": True},
    {"id": "gemini", "name": "Google Gemini", "url": "https://generativelanguage.googleapis.com/v1beta/openai",
     "local": False, "key": True},
    {"id": "openrouter", "name": "OpenRouter", "url": "https://openrouter.ai/api/v1", "local": False, "key": True},
    {"id": "groq", "name": "Groq", "url": "https://api.groq.com/openai/v1", "local": False, "key": True},
    {"id": "deepseek", "name": "DeepSeek", "url": "https://api.deepseek.com/v1", "local": False, "key": True},
    {"id": "mistral", "name": "Mistral", "url": "https://api.mistral.ai/v1", "local": False, "key": True},
    {"id": "custom", "name": "Custom (OpenAI-compatible)", "url": "", "local": None, "key": True},
]


def _headers():
    key = settings["llm_api_key"]
    headers = {"Authorization": f"Bearer {key}"}
    if "anthropic.com" in settings["llm_base_url"]:  # its /models endpoint wants the native headers
        headers |= {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return headers


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
    if offline_blocked():
        return {"online": False, "model": settings["llm_model"], "models": [], "offline_mode": True,
                "error": "offline mode: this provider is on the internet"}
    try:
        r = httpx.get(f"{_base()}/models", headers=_headers(), timeout=3)
        r.raise_for_status()
        models = [m["id"].removeprefix("models/") for m in r.json().get("data", [])]  # Gemini: "models/<id>"
    except Exception as exc:
        return {"online": False, "model": settings["llm_model"], "models": [], "error": str(exc)}
    wanted = settings["llm_model"]
    ready = wanted in models or f"{wanted}:latest" in models
    return {"online": True, "model": wanted, "model_ready": ready, "models": models}


def stream_chat(messages: list, tools: list | None = None, temperature: float | None = None,
                max_tokens: int | None = None):
    """Yield ("token", text) while streaming and finally ("tool_calls", [...]) or ("done", None).

    `messages` use the OpenAI shape (tool call arguments as JSON strings); tool calls come back as
    {"id", "name", "arguments": <json string>} whichever backend is used."""
    temperature = settings["llm_temperature"] if temperature is None else temperature
    if offline_blocked():
        raise LLMOffline("offline mode: the AI server is on the internet - choose Ollama or LM Studio")
    stream = _stream_ollama if _is_ollama() else _stream_openai
    try:
        yield from stream(messages, tools, temperature, max_tokens)
    except httpx.HTTPError as exc:
        raise LLMOffline(str(exc)) from exc


# While the app is open the model stays in VRAM (reloading costs ~7 s + re-processing the prompt ~20 s);
# unload() releases it when the window closes. 2 h is a safety net if the app crashes.
KEEP_ALIVE = "2h"  # default; Settings > Performance changes it (settings["llm_keep_alive"])


def is_local_url(url: str | None = None) -> bool:
    url = (url or settings["llm_base_url"]).lower()
    return any(h in url for h in ("//127.0.0.1", "//localhost", "//[::1]", "//0.0.0.0"))


AI_FIELDS = ("llm_preset", "llm_base_url", "llm_model", "llm_api_key", "llm_provider")
LOCAL_DEFAULT = {"llm_preset": "ollama", "llm_base_url": "http://127.0.0.1:11434/v1", "llm_model": "qwen3:8b",
                 "llm_api_key": "ollama", "llm_provider": "auto"}


def switch_target(target: str) -> bool:
    """One-click local AI <-> API (v0.14): the current fields go to their slot and the other slot is loaded.
    With an API the model runs on the provider's servers - almost no load on this PC, but the messages leave it.
    Returns True when the API still has to be configured (provider + key)."""
    target = "api" if target == "api" else "local"
    current = settings["ai_target"]
    changes = {f"ai_{current}": {k: settings[k] for k in AI_FIELDS}, "ai_target": target}
    slot = settings.get(f"ai_{target}") or {}
    changes.update(slot or (LOCAL_DEFAULT if target == "local" else {}))
    if target == "api" and settings["network_mode"] == "offline":
        changes["network_mode"] = "online"  # an API needs the internet
    settings.apply(changes)
    return target == "api" and (not slot or is_local_url())


def offline_blocked() -> bool:
    """Offline mode: a cloud AI server is never contacted."""
    return settings["network_mode"] == "offline" and not is_local_url()


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
        "keep_alive": settings.get("llm_keep_alive") or KEEP_ALIVE,
        "think": False,  # reasoning models (qwen3, deepseek-r1) answer directly: much faster for an assistant
        "options": {"temperature": temperature, "num_ctx": settings["llm_context"], **options},
    }
    if int(settings.get("llm_num_gpu", -1)) >= 0:
        body["options"]["num_gpu"] = int(settings["llm_num_gpu"])
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


def _stream_ollama(messages, tools, temperature, max_tokens=None):
    body = _native_body(messages, tools, temperature, **({"num_predict": max_tokens} if max_tokens else {}))
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


def _stream_openai(messages, tools, temperature, max_tokens=None):
    body = {"model": settings["llm_model"], "messages": messages, "stream": True, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
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
