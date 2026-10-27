"""The examiner: everything that decides whether a report got better.

Rules this file keeps, each learned from a project that broke them:
- The checklist is written from the question before any research, then frozen and fingerprinted.
- Some checklist items are held back. The writer never sees them; they are scored once, at the end.
- Claims are pulled out of the report by code, never by the writer.
- Every claim is checked against the page text that was actually fetched, not against memory.
- A new version is kept only if no main number drops and one rises by more than the noise.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import statistics
from dataclasses import dataclass, field

from .models import Model
from .sources import Source
from .text import best_passage, claims, normalise, words

KEY_METRICS = ("supported", "visible_pass", "supported_share")


@dataclass
class Checklist:
    question: str
    visible: list[str]
    hidden: list[str]
    fingerprint: str

    def to_dict(self) -> dict:
        return {"question": self.question, "visible": self.visible, "hidden": self.hidden,
                "fingerprint": self.fingerprint}


def make_checklist(examiner: Model, question: str, hidden_every: int = 3) -> tuple[Checklist, int]:
    reply = examiner.ask("checklist", {"question": question})
    items = []
    for it in reply.data.get("items", []):
        if isinstance(it, str) and it.strip() and it.strip() not in items:
            items.append(it.strip())
    # Hold back items chosen by their own fingerprint, so the split cannot be steered by the writer.
    ranked = sorted(items, key=lambda s: hashlib.sha256(s.encode()).hexdigest())
    hidden = ranked[::hidden_every] if len(items) >= hidden_every else []
    visible = [s for s in items if s not in hidden]
    fp = hashlib.sha256(json.dumps([question, visible, hidden]).encode()).hexdigest()[:16]
    return Checklist(question, visible, hidden, fp), reply.tokens


@dataclass
class Score:
    metrics: dict
    claims: list[dict] = field(default_factory=list)
    failing: list[str] = field(default_factory=list)
    tokens: int = 0

    def feedback(self) -> dict:
        """What the writer is told. Only visible items; never the hidden ones."""
        return {
            "unsupported": [c["raw"] for c in self.claims if c["cites"] and not c["supported"]],
            "uncited": [c["raw"] for c in self.claims if not c["cites"]],
            "open_points": [f.split(":", 1)[1].strip(" ?") if f.startswith("Does the report answer:") else f
                            for f in self.failing],
        }


def copied(claim: str, passage: str) -> bool:
    """True when a long claim is almost entirely one stretch pasted from the source."""
    if len(claim) < 60:
        return False
    a, b = claim.lower(), passage.lower()
    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size / len(a) >= 0.9


def score_report(report: str, question: str, items: list[str], examiner: Model, source: Source) -> Score:
    tokens = 0
    rows = []
    for c in claims(report):
        ok, was_copied = False, False
        for cid in c.cites:
            doc = source.get(cid)
            if doc is None:
                continue
            passage = best_passage(doc.text, c.text)
            was_copied = was_copied or copied(c.text, passage)
            r = examiner.ask("support", {"claim": c.text, "source": passage})
            tokens += r.tokens
            if r.data.get("supported") is True:
                ok = True
                break
        rows.append({"raw": c.raw, "cites": c.cites, "supported": ok, "copied": was_copied})
    failing = []
    for item in items:
        r = examiner.ask("check", {"question": question, "report": report, "item": item})
        tokens += r.tokens
        if r.data.get("pass") is not True:
            failing.append(item)
    n = len(rows)
    sup = sum(r["supported"] for r in rows)
    metrics = {
        "claims": n,
        "supported": sup,
        "supported_share": round(sup / n, 4) if n else 0.0,
        "uncited": sum(not r["cites"] for r in rows),
        "copied": sum(r["copied"] for r in rows),
        "visible_pass": round((len(items) - len(failing)) / len(items), 4) if items else 0.0,
        "words": len(words(report)),
    }
    return Score(metrics, rows, failing, tokens)


def noise(scores: list[Score]) -> dict:
    """How far each main number moves when the same report is scored again: the spread across repeats."""
    return {m: round(max(s.metrics[m] for s in scores) - min(s.metrics[m] for s in scores), 4)
            for m in KEY_METRICS}


def mean_score(scores: list[Score]) -> Score:
    first = scores[0]
    metrics = dict(first.metrics)
    for m in KEY_METRICS:
        metrics[m] = round(statistics.fmean(s.metrics[m] for s in scores), 4)
    return Score(metrics, first.claims, first.failing, sum(s.tokens for s in scores))


def accept(best: dict, cand: dict, margin: dict) -> tuple[bool, str]:
    for m in KEY_METRICS:
        if cand[m] < best[m] - margin[m]:
            return False, f"{m} fell from {best[m]} to {cand[m]}"
    # A higher share only counts because the supported count is already known not to have fallen,
    # so it can only come from dropping bad claims, not from saying less.
    gains = [m for m in KEY_METRICS if cand[m] > best[m] + margin[m]]
    if not gains:
        return False, "no gain bigger than the noise"
    return True, "better on " + ", ".join(gains)


def key_recall(report: str, keys: list[str]) -> float:
    text = normalise(report)
    return round(sum(normalise(k) in text for k in keys) / len(keys), 4) if keys else 0.0
