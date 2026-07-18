"""Run the suite on baseline and candidate models, diff them, emit CI verdict."""

import json
import os
import sys
from collections import defaultdict

from runner import CATEGORIES, SimulatedModel, gen_tests, load_tests, run_suite

HERE = os.path.dirname(os.path.abspath(__file__))
REGRESSION_GATE_PTS = 3.0  # fail CI if any category drops more than this


def by_category(results):
    agg = defaultdict(lambda: {"n": 0, "pass": 0.0, "consistent": 0})
    for r in results:
        a = agg[r["category"]]
        a["n"] += 1
        a["pass"] += r["pass_rate"]
        a["consistent"] += 1 if r["consistent"] else 0
    return {c: {"pass_pct": round(a["pass"] / a["n"] * 100, 1),
                "consistent_pct": round(a["consistent"] / a["n"] * 100, 1)}
            for c, a in agg.items()}


def failure_histogram(results):
    hist = defaultdict(int)
    for r in results:
        for k in r["failure_kinds"]:
            hist[k] += 1
    return dict(hist)


def main():
    gen_tests()
    tests = load_tests()
    baseline = SimulatedModel("v1.0")
    candidate = SimulatedModel("v1.1-rc")

    res_b = run_suite(baseline, tests)
    res_c = run_suite(candidate, tests)
    cat_b, cat_c = by_category(res_b), by_category(res_c)

    diff = {c: round(cat_c[c]["pass_pct"] - cat_b[c]["pass_pct"], 1) for c in CATEGORIES}
    regressions = {c: d for c, d in diff.items() if d < -REGRESSION_GATE_PTS}
    verdict = "FAIL" if regressions else "PASS"

    overall_b = round(sum(r["pass_rate"] for r in res_b) / len(res_b) * 100, 1)
    overall_c = round(sum(r["pass_rate"] for r in res_c) / len(res_c) * 100, 1)

    flaky = [r["id"] for r in res_c if 0 < r["pass_rate"] < 1]

    data = {
        "n_tests": len(tests),
        "runs_per_test": tests[0]["runs"],
        "models": ["v1.0", "v1.1-rc"],
        "overall": {"v1.0": overall_b, "v1.1-rc": overall_c},
        "categories": CATEGORIES,
        "by_category": {"v1.0": cat_b, "v1.1-rc": cat_c},
        "diff": diff,
        "regressions": regressions,
        "verdict": verdict,
        "gate_pts": REGRESSION_GATE_PTS,
        "failure_hist": {"v1.0": failure_histogram(res_b), "v1.1-rc": failure_histogram(res_c)},
        "flaky_tests": flaky,
        "worst_tests": sorted(res_c, key=lambda r: r["pass_rate"])[:10],
    }

    with open(os.path.join(HERE, "results", "results.json"), "w") as f:
        json.dump(data, f, indent=2)
    with open(os.path.join(HERE, "dashboard", "data.js"), "w") as f:
        f.write("window.DATA = " + json.dumps(data) + ";\n")

    print(f"suite: {len(tests)} tests x {tests[0]['runs']} runs")
    print(f"overall pass: v1.0={overall_b}%  v1.1-rc={overall_c}%")
    print(f"category diff: {diff}")
    print(f"CI verdict: {verdict}  regressions beyond {REGRESSION_GATE_PTS} pts: {regressions}")
    sys.exit(1 if verdict == "FAIL" else 0)


if __name__ == "__main__":
    main()
