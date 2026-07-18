"""ReasonBench CI: spec loader, model interface, checks, and test runner."""

import glob
import hashlib
import json
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def stable_seed(*parts):
    """Deterministic across processes, unlike the built-in hash() of strings
    (which is salted by PYTHONHASHSEED). Keeps experiments reproducible."""
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)

CATEGORIES = ["arithmetic", "causal", "counterfactual", "temporal",
              "multi-hop", "instruction-following", "adversarial"]


# ---------------------------------------------------------------- test corpus

def gen_tests():
    """Synthesize a small but structured suite into tests/<category>/.

    In real use these are hand-written; the generator keeps the demo suite
    reproducible and shows the intended directory layout.
    """
    rng = random.Random(11)
    for cat in CATEGORIES:
        d = os.path.join(HERE, "tests", cat)
        os.makedirs(d, exist_ok=True)
        for i in range(6):
            a, b, c = rng.randint(3, 19), rng.randint(2, 9), rng.randint(11, 60)
            spec = {
                "id": f"{cat}-{i:02d}",
                "category": cat,
                "difficulty": 1 + i % 3,
                "input": f"[{cat}] If x={a} and y={b}, and the total budget is {c}, "
                         "reason step by step and give only the final number.",
                "expected_answer": str(a * b + c),
                "forbidden_patterns": ["as an AI", "I cannot", "impossible to say"],
                "max_tokens": 350 + 100 * (i % 3),
                "runs": 5,
            }
            with open(os.path.join(d, spec["id"] + ".json"), "w") as f:
                json.dump(spec, f, indent=2)


def load_tests():
    tests = []
    for path in sorted(glob.glob(os.path.join(HERE, "tests", "*", "*.json"))):
        with open(path) as f:
            tests.append(json.load(f))
    return tests


# ---------------------------------------------------------------- models

class Model:
    name = "base"

    def generate(self, prompt: str, seed: int):
        """Return (answer_text, tokens_used)."""
        raise NotImplementedError


class SimulatedModel(Model):
    """Seeded failure profiles per category, distinct per version.

    v1.1-rc improves arithmetic and multi-hop but regresses on
    instruction-following and temporal, and gets slightly more verbose,
    so the runner has real regressions to catch.
    """

    PROFILES = {
        "v1.0": {
            "wrong": {"arithmetic": 0.18, "causal": 0.22, "counterfactual": 0.30,
                      "temporal": 0.20, "multi-hop": 0.34, "instruction-following": 0.10,
                      "adversarial": 0.38},
            "flip": 0.10, "refuse": 0.03, "verbosity": 1.0,
        },
        "v1.1-rc": {
            "wrong": {"arithmetic": 0.08, "causal": 0.20, "counterfactual": 0.27,
                      "temporal": 0.31, "multi-hop": 0.22, "instruction-following": 0.24,
                      "adversarial": 0.36},
            "flip": 0.13, "refuse": 0.02, "verbosity": 1.15,
        },
    }

    def __init__(self, version: str):
        self.name = version
        self.p = self.PROFILES[version]

    def generate(self, prompt: str, seed: int):
        rng = random.Random(stable_seed(self.name, prompt, seed))
        cat = re.match(r"\[([a-z-]+)\]", prompt).group(1)
        m = re.search(r"x=(\d+) and y=(\d+).*budget is (\d+)", prompt)
        a, b, c = map(int, m.groups())
        correct = a * b + c
        tokens = int(rng.gauss(220, 60) * self.p["verbosity"])

        if rng.random() < self.p["refuse"]:
            return "I cannot answer this question.", max(20, tokens // 4)
        wrong_p = self.p["wrong"][cat]
        if rng.random() < self.p["flip"]:
            wrong_p = min(0.95, wrong_p * 2.5)  # unstable test: error rate spikes
        if rng.random() < wrong_p:
            ans = correct + rng.choice([-10, -1, 1, 2, 10, a, -b])
        else:
            ans = correct
        return f"Step by step: {a}*{b}={a*b}, plus {c} gives {ans}. Final answer: {ans}", max(30, tokens)


class APIModel(Model):
    """Adapter for a real endpoint; implement generate() with your client."""

    def __init__(self, name, base_url, api_key=""):
        self.name, self.base_url, self.api_key = name, base_url, api_key

    def generate(self, prompt, seed):
        raise NotImplementedError("wire this to /v1/chat/completions")


# ---------------------------------------------------------------- checks

def extract_answer(text: str):
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    return nums[-1] if nums else None


def check_run(spec, text, tokens):
    failures = []
    if extract_answer(text) != spec["expected_answer"]:
        failures.append("wrong_answer")
    for pat in spec.get("forbidden_patterns", []):
        if re.search(pat, text, re.I):
            failures.append("forbidden_behavior")
            break
    for pat in spec.get("required_patterns", []):
        if not re.search(pat, text, re.I):
            failures.append("missing_required")
            break
    if tokens > spec["max_tokens"]:
        failures.append("token_budget_exceeded")
    return failures


def run_suite(model: Model, tests):
    results = []
    for spec in tests:
        answers, fail_kinds, per_run_pass = [], [], []
        for r in range(spec["runs"]):
            text, tokens = model.generate(spec["input"], seed=r)
            fails = check_run(spec, text, tokens)
            answers.append(extract_answer(text))
            fail_kinds += fails
            per_run_pass.append(not fails)
        consistent = len(set(answers)) == 1
        results.append({
            "id": spec["id"], "category": spec["category"],
            "difficulty": spec["difficulty"],
            "pass_rate": sum(per_run_pass) / spec["runs"],
            "passed": all(per_run_pass),
            "consistent": consistent,
            "failure_kinds": sorted(set(fail_kinds)),
        })
    return results
