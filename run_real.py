"""ReasonBench CI against REAL models.

Each model is treated as a "version under test": the suite runs N times per test,
scoring pass rate per category, answer consistency across repeats, and a CI
regression gate comparing each candidate model against a chosen baseline.

    set -a; source ../real-benchmark/keys.env; set +a
    python3 run_real.py                  # every provider with a key
    python3 run_real.py --models "openai:gpt-4o-mini,grok:grok-4.3"
    python3 run_real.py --runs 3
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

import realrun
from real_tests import CATEGORIES, TESTS

HERE = os.path.dirname(os.path.abspath(__file__))
GATE_PTS = 10.0  # CI fails a candidate if any category drops more than this


def normalize(text):
    """Extract a comparable answer from a model response."""
    t = (text or "").strip()
    t = re.sub(r"^```[a-z]*\n?|\n?```$", "", t).strip()
    t = t.strip().strip(".!\"'` \n")
    return t


def matches(response, expected):
    """True if the response conveys the expected answer."""
    got = normalize(response)
    exp = expected.strip()
    if not got:
        return False
    if got.lower() == exp.lower():
        return True
    # numeric answers: compare the last number in the response
    if re.fullmatch(r"-?\d+(\.\d+)?", exp):
        nums = re.findall(r"-?\d+(?:\.\d+)?", got.replace(",", ""))
        return bool(nums) and abs(float(nums[-1]) - float(exp)) < 1e-9
    # HH:MM answers
    if re.fullmatch(r"\d{1,2}:\d{2}", exp):
        m = re.findall(r"\d{1,2}:\d{2}", got)
        return bool(m) and m[-1].lstrip("0") == exp.lstrip("0")
    # Word / mixed answers (Yes, Sam, Tokyo, BANANA, "April 1"): require the
    # expected phrase to appear as a whole token sequence in the response.
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(exp)}(?![A-Za-z0-9])",
                     got, re.I) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None)
    ap.add_argument("--runs", type=int, default=2,
                    help="repeats per test (consistency measurement)")
    ap.add_argument("--baseline", default=None,
                    help="model label to treat as the CI baseline")
    args = ap.parse_args()

    models = realrun.models_from_args(args.models)
    if not models:
        print("No API keys found. Source your keys.env first.")
        sys.exit(2)

    prompts = [t[2] for t in TESTS]
    results = {}

    for provider, model in models:
        lab = realrun.label(provider, model)
        print(f"\n=== {lab} ===  ({len(TESTS)} tests x {args.runs} runs)")
        # per-test list of responses across runs
        per_test = defaultdict(list)
        errors = 0
        for run_i in range(args.runs):
            # temperature 0 where supported keeps this a capability test, not a
            # sampling test; Anthropic ignores the value (its API rejects non-default).
            out = realrun.run_prompts(provider, model, prompts, max_tokens=120,
                                      temperature=0)
            for (tid, cat, _p, exp), (text, err) in zip(TESTS, out):
                if err:
                    errors += 1
                per_test[tid].append(text)
            print(f"  run {run_i + 1}/{args.runs} done")

        by_cat = defaultdict(lambda: {"pass": 0, "n": 0})
        consistent_tests = 0
        failures = []
        for tid, cat, _p, exp in TESTS:
            responses = per_test[tid]
            passes = sum(1 for r in responses if matches(r, exp))
            by_cat[cat]["pass"] += passes
            by_cat[cat]["n"] += len(responses)
            # consistent = every repeat produced the same normalized answer
            if len(set(normalize(r).lower() for r in responses)) == 1:
                consistent_tests += 1
            if passes < len(responses):
                failures.append({"id": tid, "category": cat,
                                 "expected": exp,
                                 "got": normalize(responses[0])[:80],
                                 "pass_rate": round(passes / len(responses) * 100)})

        cat_pct = {c: round(by_cat[c]["pass"] / by_cat[c]["n"] * 100, 1)
                   for c in CATEGORIES if by_cat[c]["n"]}
        total_pass = sum(v["pass"] for v in by_cat.values())
        total_n = sum(v["n"] for v in by_cat.values())
        results[lab] = {
            "overall_pct": round(total_pass / total_n * 100, 1),
            "by_category": cat_pct,
            "consistency_pct": round(consistent_tests / len(TESTS) * 100, 1),
            "errors": errors,
            "failures": failures[:12],
        }
        print(f"  overall {results[lab]['overall_pct']}%  "
              f"consistency {results[lab]['consistency_pct']}%  errors {errors}")

    # ---- CI gate: compare each candidate against the baseline -------------
    labels = list(results)
    baseline = args.baseline if args.baseline in results else (
        max(labels, key=lambda l: results[l]["overall_pct"]))
    gate = {}
    for lab in labels:
        if lab == baseline:
            continue
        diffs = {c: round(results[lab]["by_category"].get(c, 0)
                          - results[baseline]["by_category"].get(c, 0), 1)
                 for c in CATEGORIES if c in results[baseline]["by_category"]}
        regress = {c: d for c, d in diffs.items() if d < -GATE_PTS}
        gate[lab] = {"diff": diffs, "regressions": regress,
                     "verdict": "FAIL" if regress else "PASS"}

    data = {
        "data_source": "real API calls",
        "n_tests": len(TESTS), "runs_per_test": args.runs,
        "gate_pts": GATE_PTS, "baseline": baseline,
        "categories": CATEGORIES,
        "models": labels, "results": results, "gate": gate,
    }
    realrun.save(HERE, data)

    print(f"\nbaseline: {baseline}")
    for lab, g in gate.items():
        print(f"  {lab}: {g['verdict']}  regressions={g['regressions']}")
    print("wrote results/results.json and dashboard/data.js")


if __name__ == "__main__":
    main()
