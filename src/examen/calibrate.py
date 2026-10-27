"""Measure the examiner before trusting it.

The labels are made by construction from the invented corpus: a true claim is a sentence copied
from its page; a false claim is the same sentence with one number or one name swapped. Nobody has
to hand-label anything, and the right answer is known for every pair.
"""
from __future__ import annotations

import random
import re

from .models import Model
from .sources import load_corpus
from .text import best_passage, sentences

TRUST_BAR = 0.85
# For a self-grader the costly mistake is waving a false claim through, so that gets its own limit.
FALSE_PASS_LIMIT = 0.10
NUM = re.compile(r"\b\d[\d,]*\b")
NAME = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")


def make_labels(n: int = 60, seed: int = 7) -> list[dict]:
    corpus = load_corpus()
    rng = random.Random(seed)
    names = sorted({m for d in corpus["docs"] for m in NAME.findall(d["text"])})
    pairs = []
    for d in corpus["docs"]:
        for s in sentences(d["text"]):
            nums, found = NUM.findall(s), NAME.findall(s)
            false = None
            if nums:
                old = rng.choice(nums)
                digits = old.replace(",", "")
                new = str(int(digits) + rng.choice([3, 7, 11, 19]))
                false = s.replace(old, new, 1)
            elif found:
                old = rng.choice(found)
                others = [x for x in names if x != old and x not in s]
                if others:
                    false = s.replace(old, rng.choice(others), 1)
            if false and false != s:
                pairs.append((d, s, false))
    rng.shuffle(pairs)
    out = []
    for d, true, false in pairs[: n // 2]:
        out.append({"claim": true, "source": best_passage(d["text"], true), "label": True, "doc": d["id"]})
        out.append({"claim": false, "source": best_passage(d["text"], true), "label": False, "doc": d["id"]})
    return out


def calibrate(examiner: Model, labels: list[dict], runs: int = 2) -> dict:
    verdicts = [[examiner.ask("support", {"claim": x["claim"], "source": x["source"]}).data.get("supported") is True
                 for x in labels] for _ in range(runs)]
    first = verdicts[0]
    right = sum(v == x["label"] for v, x in zip(first, labels))
    fp = sum(v and not x["label"] for v, x in zip(first, labels))
    fn = sum((not v) and x["label"] for v, x in zip(first, labels))
    same = sum(all(r[i] == first[i] for r in verdicts) for i in range(len(labels)))
    acc = right / len(labels) if labels else 0.0
    n_false = sum(not x["label"] for x in labels)
    false_pass = fp / n_false if n_false else 0.0
    return {
        "examiner": examiner.name, "pairs": len(labels), "accuracy": round(acc, 4),
        "passed_false_claims": fp, "rejected_true_claims": fn,
        "self_agreement": round(same / len(labels), 4) if labels else 0.0,
        "false_pass_rate": round(false_pass, 4),
        "trusted": acc >= TRUST_BAR and false_pass <= FALSE_PASS_LIMIT,
        "bar": {"accuracy": TRUST_BAR, "false_pass_rate": FALSE_PASS_LIMIT},
    }
