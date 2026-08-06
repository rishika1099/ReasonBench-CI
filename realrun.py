"""Shared helper for running portfolio experiments against REAL models.

Every converted project imports this so they share one tested code path for
model selection, parallelism, retry/backoff, and result persistence.

Model selection order:
  1. --models CLI arg, or the BENCH_MODELS env var  ("openai:gpt-4o-mini,grok:grok-4.3")
  2. CHEAP defaults, filtered to providers that actually have an API key set

Usage inside a project runner:

    from realrun import models_from_args, run_many, save

    models = models_from_args()
    rows = run_many(models, prompts, max_tokens=64)
"""

import concurrent.futures as cf
import json
import os
import time

import providers

# Cheap tier per provider: real models, minimal spend.
CHEAP = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-4.3",
}

# Gemini's free tier has a very low requests-per-minute cap; calling it in
# parallel just produces 429 storms. Providers listed here run serially.
SERIAL_PROVIDERS = {"gemini"}


def models_from_args(argv_models=None, exclude=()):
    """Return [(provider, model), ...] for providers that have a key set."""
    spec = argv_models or os.environ.get("BENCH_MODELS")
    if spec:
        out = []
        for item in spec.split(","):
            p, _, m = item.strip().partition(":")
            if p and p not in exclude:
                out.append((p, m or CHEAP.get(p)))
        return out
    have = set(providers.available_providers())
    return [(p, m) for p, m in CHEAP.items() if p in have and p not in exclude]


def label(provider, model):
    return f"{provider}:{model}"


def ask(provider, model, prompt, max_tokens=256, system=None, temperature=0.7,
        retries=2):
    """One call, returning text ('' on failure) plus an error string if any."""
    for attempt in range(retries + 1):
        try:
            r = providers.chat(provider, model, prompt, system=system,
                               max_tokens=max_tokens, temperature=temperature)
            return r["text"], None
        except Exception as e:
            msg = str(e)[:200]
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            return "", msg
    return "", "unreachable"


def run_prompts(provider, model, prompts, max_tokens=256, system=None,
                temperature=0.7, workers=4):
    """Run a list of prompts against one model. Returns list of (text, error).

    Order is preserved. Gemini runs serially to respect its free-tier limit.
    """
    if provider in SERIAL_PROVIDERS:
        workers = 1
    results = [None] * len(prompts)
    if workers <= 1:
        for i, p in enumerate(prompts):
            results[i] = ask(provider, model, p, max_tokens, system, temperature)
        return results
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(ask, provider, model, p, max_tokens, system,
                          temperature): i for i, p in enumerate(prompts)}
        for f in cf.as_completed(futs):
            results[futs[f]] = f.result()
    return results


def save(here, data, merge_key="results"):
    """Write results/results.json + dashboard/data.js, merging prior model rows."""
    rp = os.path.join(here, "results", "results.json")
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    if merge_key and os.path.exists(rp):
        try:
            prev = json.load(open(rp))
            prior = prev.get(merge_key, {})
            # Only carry forward rows from a prior REAL run, and only rows keyed
            # like "provider:model". This prevents old simulated result rows from
            # silently mixing into real measurements.
            if (isinstance(prior, dict) and isinstance(data.get(merge_key), dict)
                    and prev.get("data_source") == "real API calls"):
                prior = {k: v for k, v in prior.items() if ":" in k}
                data[merge_key] = {**prior, **data[merge_key]}
                if "models" in data:
                    data["models"] = list(data[merge_key])
        except Exception:
            pass
    data.setdefault("generated_at", time.strftime("%Y-%m-%d %H:%M"))
    data.setdefault("data_source", "real API calls")
    with open(rp, "w") as f:
        json.dump(data, f, indent=2)
    with open(os.path.join(here, "dashboard", "data.js"), "w") as f:
        f.write("window.DATA = " + json.dumps(data) + ";\n")
    return rp
