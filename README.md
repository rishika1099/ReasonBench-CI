# ReasonBench CI

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
