"""Unified, dependency-free adapter for OpenAI, Anthropic (Claude), Google Gemini,
and xAI (Grok). Standard library only: no SDKs to install.

Every project in this portfolio defaults to its deterministic SimulatedBackend so
the repo runs with zero cost and zero keys. To run against a real model, set the
relevant API key in the environment and pass a provider to the project's runner:

    export OPENAI_API_KEY=sk-...
    export ANTHROPIC_API_KEY=sk-ant-...
    export GEMINI_API_KEY=...
    export XAI_API_KEY=xai-...

    from providers import chat, stream_chat
    text = chat("anthropic", "claude-sonnet-5", "Say hi")

`chat()` returns the completion text and token usage. `stream_chat()` yields
(chunk_text, timestamp) tuples so latency-oriented projects (TTFT / inter-token
latency) can measure real streaming behavior.

This module makes real network calls to paid third-party APIs when invoked with a
provider. It never runs on import and is never on the default path.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

# Sensible current defaults per provider; override by passing an explicit model.
# Anthropic model IDs: claude-opus-4-8, claude-sonnet-5, claude-haiku-4-5.
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-4.3",
}

_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "grok": "https://api.x.ai/v1/chat/completions",
    # gemini path includes the model, filled in per call
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
}

_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "grok": "XAI_API_KEY",
}


class ProviderError(RuntimeError):
    pass


def _key(provider):
    env = _KEY_ENV[provider]
    k = os.environ.get(env)
    if not k:
        raise ProviderError(f"{env} is not set; export it to call {provider}.")
    return k


def _retry_delay(body_text, default):
    """Honor a server-provided retry delay (Gemini RetryInfo / Retry-After)."""
    m = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', body_text)
    return int(m.group(1)) if m else default


def _post(url, headers, payload, timeout=60, max_retries=4):
    data = json.dumps(payload).encode()
    backoff = 5
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            text = e.read().decode()
            # 429 (rate limit) and 5xx are retryable; back off and try again
            if e.code in (429, 500, 502, 503, 529) and attempt < max_retries:
                wait = min(_retry_delay(text, backoff), 65)
                time.sleep(wait)
                backoff *= 2
                continue
            raise ProviderError(f"HTTP {e.code}: {text[:300]}")


def chat(provider, model=None, prompt="", system=None, max_tokens=512,
         temperature=0.7, timeout=60):
    """Single-shot completion. Returns {text, tokens_in, tokens_out, model}."""
    provider = provider.lower()
    model = model or DEFAULT_MODELS[provider]

    if provider in ("openai", "grok"):
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        body = _post(_ENDPOINTS[provider],
                     {"Authorization": f"Bearer {_key(provider)}",
                      "Content-Type": "application/json"},
                     {"model": model, "messages": msgs,
                      "max_tokens": max_tokens, "temperature": temperature}, timeout)
        u = body.get("usage", {})
        return {"text": body["choices"][0]["message"]["content"],
                "tokens_in": u.get("prompt_tokens"), "tokens_out": u.get("completion_tokens"),
                "model": model}

    if provider == "anthropic":
        # Newer Anthropic models (Sonnet 5, Opus 4.8, Fable 5) reject a non-default
        # temperature with a 400, so we omit it and let the model use its default.
        payload = {"model": model, "max_tokens": max_tokens,
                   "messages": [{"role": "user", "content": prompt}]}
        if system:
            payload["system"] = system
        body = _post(_ENDPOINTS["anthropic"],
                     {"x-api-key": _key("anthropic"),
                      "anthropic-version": "2023-06-01",
                      "Content-Type": "application/json"}, payload, timeout)
        u = body.get("usage", {})
        return {"text": "".join(b.get("text", "") for b in body["content"]),
                "tokens_in": u.get("input_tokens"), "tokens_out": u.get("output_tokens"),
                "model": model}

    if provider == "gemini":
        url = _ENDPOINTS["gemini"].format(model=model) + f"?key={_key('gemini')}"
        # thinkingBudget:0 turns off the 2.5 "thinking" phase so a small token
        # budget yields a direct answer instead of being spent on hidden reasoning.
        payload = {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"maxOutputTokens": max_tokens,
                                        "temperature": temperature,
                                        "thinkingConfig": {"thinkingBudget": 0}}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        body = _post(url, {"Content-Type": "application/json"}, payload, timeout)
        cands = body.get("candidates", [])
        if not cands:
            raise ProviderError(f"gemini returned no candidates: {json.dumps(body)[:200]}")
        # 2.5 models are "thinking" models; a candidate may lack content.parts
        # (thinking-only turn, or a non-STOP finishReason). Handle gracefully.
        parts = cands[0].get("content", {}).get("parts", []) or []
        text = "".join(p.get("text", "") for p in parts)
        u = body.get("usageMetadata", {})
        return {"text": text, "tokens_in": u.get("promptTokenCount"),
                "tokens_out": u.get("candidatesTokenCount"), "model": model}

    raise ProviderError(f"unknown provider: {provider}")


def stream_chat(provider, model=None, prompt="", timeout=60, **kw):
    """Yield (chunk_text, monotonic_ts) for streaming latency measurement.

    Implemented for the OpenAI-compatible providers (openai, grok) via SSE.
    For anthropic/gemini, wire their streaming endpoints the same way. Falls back
    to a single yield for providers without streaming here.
    """
    provider = provider.lower()
    model = model or DEFAULT_MODELS[provider]

    if provider == "anthropic":
        # Real SSE streaming so TTFT is comparable with the OpenAI-style providers.
        payload = {"model": model, "max_tokens": kw.get("max_tokens", 512),
                   "stream": True,
                   "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            _ENDPOINTS["anthropic"], data=json.dumps(payload).encode(),
            headers={"x-api-key": _key("anthropic"),
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "content_block_delta":
                    piece = ev.get("delta", {}).get("text", "")
                    if piece:
                        yield piece, time.monotonic()
        return

    if provider == "gemini":
        # Gemini streaming endpoint (SSE).
        url = (_ENDPOINTS["gemini"].format(model=model)
               .replace(":generateContent", ":streamGenerateContent")
               + f"?alt=sse&key={_key('gemini')}")
        payload = {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"maxOutputTokens": kw.get("max_tokens", 512),
                                        "thinkingConfig": {"thinkingBudget": 0}}}
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                for c in ev.get("candidates", []):
                    for p in c.get("content", {}).get("parts", []) or []:
                        if p.get("text"):
                            yield p["text"], time.monotonic()
        return

    msgs = [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": msgs, "stream": True,
               "max_tokens": kw.get("max_tokens", 512)}
    req = urllib.request.Request(
        _ENDPOINTS[provider], data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {_key(provider)}",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content", "")
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
            if delta:
                yield delta, time.monotonic()


def available_providers():
    """Which providers have a key set right now."""
    return [p for p, env in _KEY_ENV.items() if os.environ.get(env)]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Smoke-test a provider adapter.")
    ap.add_argument("provider", choices=list(DEFAULT_MODELS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--prompt", default="Reply with exactly: OK")
    args = ap.parse_args()
    print(f"keys present: {available_providers()}")
    r = chat(args.provider, args.model, args.prompt, max_tokens=32)
    print(f"[{r['model']}] {r['text']!r}  (in={r['tokens_in']} out={r['tokens_out']})")
