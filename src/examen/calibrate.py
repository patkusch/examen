"""Measure the examiner before trusting it.

The labels are made by construction from the invented corpus: a true claim is a sentence copied
from its page; a false claim is the same sentence with one small change: a number or a name
swapped, a "not" added, or a made-up detail tacked on. Nobody has to hand-label anything, and
the right answer is known for every pair. Results are broken down by kind of change, because
an examiner that catches swapped numbers can still miss an added "not".
"""
from __future__ import annotations

import random
import re

from .models import Model
from .sources import load_corpus
from .text import best_passage, sentences, truthy

TRUST_BAR = 0.85
# For a self-grader the costly mistake is waving a false claim through, so that gets its own limit.
FALSE_PASS_LIMIT = 0.10
# Rejecting a true sentence is not harmless either: the loop then deletes a true fact.
FALSE_REJECT_LIMIT = 0.15
LEAD_IN = "The {title} page records this: "
NUM = re.compile(r"\b\d[\d,]*\b")
NAME = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")


PADDING = ", after a long dispute with the mainland government"
NEGATE = re.compile(r"\b(is|was|are|were|has|had|can)\b")
VERBS = {"built": "demolished", "founded": "closed", "won": "lost", "restored": "demolished", "rebuilt": "abandoned",
         "began": "ended", "retired": "returned", "designed": "copied", "created": "abolished", "hosts": "banned",
         "runs": "sold", "sells": "buys", "arrive": "leave", "automated": "abandoned", "trained": "taught",
         "moved": "returned", "campaigned": "argued", "destroyed": "spared", "named": "renamed", "raised": "lost"}
PLACES = ["Halvey", "Ostra", "Kessick", "Aberlin", "Tarrin", "Mardale"]
COUNTS = {"two": "three", "three": "four", "four": "six", "nine": "seven", "twelve": "ten", "ten": "twelve"}
# Kinds examen's code checks were built to catch, and kinds held out from them. An examiner must pass
# the held-out kinds on their own too, so code checks cannot simply be fitted to the test.
TARGETED = ("number", "name", "negation", "padding")
HELD_OUT = ("verb", "place", "count_word")
KINDS = TARGETED + HELD_OUT


def _falsify(kind: str, s: str, rng: random.Random, names: list[str]) -> str | None:
    """Make a false version of a true sentence by one small, realistic change."""
    if kind == "number":
        nums = NUM.findall(s)
        if not nums:
            return None
        old = rng.choice(nums)
        return s.replace(old, str(int(old.replace(",", "")) + rng.choice([3, 7, 11, 19])), 1)
    if kind == "name":
        found = NAME.findall(s)
        others = [x for x in names if x not in s]
        if not found or not others:
            return None
        return s.replace(rng.choice(found), rng.choice(others), 1)
    if kind == "negation":
        m = NEGATE.search(s)
        return s[: m.end()] + " not" + s[m.end():] if m else None
    if kind == "padding":  # true sentence plus a made-up detail
        return s.rstrip(".") + PADDING + "."
    if kind == "verb":
        m = re.search(r"\b(" + "|".join(VERBS) + r")\b", s)
        return s[: m.start()] + VERBS[m.group(1)] + s[m.end():] if m else None
    if kind == "place":
        found = [p for p in PLACES if re.search(rf"\b{p}\b", s)]
        if not found:
            return None
        old = rng.choice(found)
        return re.sub(rf"\b{old}\b", rng.choice([p for p in PLACES if p not in s]), s, count=1)
    if kind == "count_word":
        m = re.search(r"\b(" + "|".join(COUNTS) + r")\b", s)
        return s[: m.start()] + COUNTS[m.group(1)] + s[m.end():] if m else None
    raise ValueError(kind)


def make_labels(n: int = 84, seed: int = 7) -> list[dict]:
    """n/2 true claims copied from pages, n/2 false ones, the false kinds taking turns."""
    corpus = load_corpus()
    rng = random.Random(seed)
    names = sorted({m for d in corpus["docs"] for m in NAME.findall(d["text"])})
    pool = [(d, s) for d in corpus["docs"] for s in sentences(d["text"])]
    rng.shuffle(pool)
    out, used = [], set()
    for i in range(n // 2):
        kind = KINDS[i % len(KINDS)]
        for j, (d, true) in enumerate(pool):
            false = None if j in used else _falsify(kind, true, rng, names)
            if false and false != true:
                used.add(j)
                passage = best_passage(d["text"], true)
                # Every other true claim is reworded, so the examiner is tested on writing that is not a paste.
                if i % 2:
                    out.append({"claim": LEAD_IN.format(title=d["title"]) + true, "source": passage, "label": True,
                                "kind": "reworded", "doc": d["id"]})
                else:
                    out.append({"claim": true, "source": passage, "label": True, "kind": "verbatim", "doc": d["id"]})
                out.append({"claim": false, "source": passage, "label": False, "kind": kind, "doc": d["id"]})
                break
    return out[:n]


def calibrate(examiner: Model, labels: list[dict], runs: int = 2) -> dict:
    """Accuracy and error rates come from the first run; self-agreement compares runs made with
    different seeds, so it shows how often the examiner changes its mind on the same claim."""
    verdicts = [[truthy(examiner.vary(r).ask("support", {"claim": x["claim"], "source": x["source"]})
                        .data.get("supported")) for x in labels] for r in range(runs)]
    first = verdicts[0]
    vetoes = getattr(examiner, "vetoes", None)
    right = sum(v == x["label"] for v, x in zip(first, labels))
    fp = sum(v and not x["label"] for v, x in zip(first, labels))
    fn = sum((not v) and x["label"] for v, x in zip(first, labels))
    same = sum(all(r[i] == first[i] for r in verdicts) for i in range(len(labels)))
    acc = right / len(labels) if labels else 0.0
    n_false = sum(not x["label"] for x in labels)
    false_pass = fp / n_false if n_false else 0.0
    n_true = len(labels) - n_false
    false_reject = fn / n_true if n_true else 0.0
    held = [(v, x) for v, x in zip(first, labels) if x["kind"] in HELD_OUT]
    held_pass = sum(v for v, _ in held) / len(held) if held else 0.0
    return {
        "examiner": examiner.name, "pairs": len(labels), "accuracy": round(acc, 4),
        "passed_false_claims": fp, "rejected_true_claims": fn,
        "self_agreement": round(same / len(labels), 4) if labels else 0.0,
        "false_pass_rate": round(false_pass, 4),
        "false_pass_by_kind": {k: f"{sum(v for v, x in zip(first, labels) if x['kind'] == k)} of "
                                  f"{sum(x['kind'] == k for x in labels)}"
                               for k in KINDS if any(x['kind'] == k for x in labels)},
        "false_reject_rate": round(false_reject, 4),
        "false_reject_by_kind": {k: f"{sum(not v for v, x in zip(first, labels) if x['kind'] == k)} of "
                                    f"{sum(x['kind'] == k for x in labels)}"
                                 for k in ("verbatim", "reworded") if any(x['kind'] == k for x in labels)},
        "held_out_false_pass_rate": round(held_pass, 4),
        # How many first-run verdicts code made without asking the model (guarded examiners only).
        "decided_by_code": vetoes,
        "trusted": (acc >= TRUST_BAR and false_pass <= FALSE_PASS_LIMIT and false_reject <= FALSE_REJECT_LIMIT
                    and held_pass <= FALSE_PASS_LIMIT),
        "bar": {"accuracy": TRUST_BAR, "false_pass_rate": FALSE_PASS_LIMIT, "false_reject_rate": FALSE_REJECT_LIMIT,
                "held_out_false_pass_rate": FALSE_PASS_LIMIT},
    }
