# ReasonBench CI

> **These results are REAL.** Measured 2026-08-05 20:35 via live API calls against
> **gpt-4o-mini, claude-haiku-4-5, grok-4.3** (24 verifiable reasoning tests x 2 runs across 6 categories). Reproduce with:
> `set -a; source ../real-benchmark/keys.env; set +a && python3 run_real.py`
> The original simulated runner is kept alongside for the zero-cost/no-key path.


Regression testing for LLM reasoning, modeled on unit testing: declarative test specs,
a runner, per-category reports, and model-version diffing so a CI pipeline can fail a
deploy when reasoning quality regresses.

## Test spec format

Tests live in `tests/<category>/*.json`:

```json
{
  "id": "arith-multi-step-01",
  "category": "arithmetic",
  "difficulty": 2,
  "input": "A store sells pens at $3 each...",
  "expected_answer": "42",
  "forbidden_patterns": ["as an AI", "cannot answer"],
  "required_patterns": [],
  "max_tokens": 400,
  "runs": 5
}
```

## What the runner detects

- Wrong final answers (exact or normalized numeric match)
- Inconsistency: answers that flip across repeated runs of the same test
- Token-budget violations (reasoning that rambles past `max_tokens`)
- Forbidden behavior (refusals, hedging, banned phrases)
- Per-category regressions between two model versions

## Architecture

- `runner.py`: loads specs, executes N runs per test against a `Model`, applies checks,
  emits a JUnit-style summary. The `Model` interface is one `generate(prompt)` call;
  `SimulatedModel` ships two versions ("v1.0" and "v1.1-rc") with different seeded
  failure profiles per category so regression detection is exercised end to end.
  Point `APIModel` at any real endpoint to test actual models.
- `run_experiments.py`: runs both versions over the full suite, computes pass rates,
  flip rates, and the regression diff, and writes the dashboard data.

## Run

```bash
python3 run_experiments.py
open dashboard/index.html
```

Exit code is nonzero if the candidate version regresses more than 3 points on any
category, which is the CI gate.

## Evaluate against a real model

`providers.py` (vendored, standard-library only) is a unified adapter for
**OpenAI, Anthropic (Claude), Google Gemini, and xAI (Grok)**. Set the relevant
key and the simulated backend can be swapped for a live model:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY / GEMINI_API_KEY / XAI_API_KEY
python3 -c "from providers import chat; print(chat('anthropic','claude-sonnet-5','Say hi'))"
```

The simulated path remains the default so the repo runs with zero cost and no keys.
Real calls hit paid third-party APIs; nothing contacts a network unless you pass a
provider explicitly.
