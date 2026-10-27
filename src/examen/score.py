"""The examiner: everything that decides whether a report got better.

Rules this file keeps, each learned from a project that broke them:
- The checklist is written from the question before any research, then frozen and fingerprinted.
- Some checklist items are held back. The writer never hears about them; they are scored once, at the end.
  Items about citing are never held back, because the writer is always told which sentences lack a source.
- Claims are pulled out of the report by code, never by the writer.
- Every claim is checked against the page text that was actually fetched in this run, not against memory.
- A sentence citing several pages is checked against all of them together, once, so extra
  citations do not buy extra chances to pass. Citing more than three pages counts as unsupported.
- A new version is kept only if no main number drops (against the best so far and against the
  first draft), it copies no more than before, and the checklist or the backed share rises by
  more than the noise.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import statistics
from dataclasses import dataclass, field

from .models import Model
from .sources import Source
from .text import best_passage, claims, normalise, truthy, words

KEY_METRICS = ("supported", "visible_pass", "supported_share")
GAIN_METRICS = ("visible_pass", "supported_share")  # a bigger count alone is not a better report
MAX_CITES = 3
ABOUT_CITING = re.compile(r"\b(source|sources|cite|cites|cited|citation|citations|reference|references)\b", re.I)


@dataclass
class Checklist:
    question: str
    visible: list[str]
    hidden: list[str]
    fingerprint: str

    def to_dict(self) -> dict:
        return {"question": self.question, "visible": self.visible, "hidden": self.hidden,
                "fingerprint": self.fingerprint}


def make_checklist(examiner: Model, question: str, hold_back: float = 1 / 3, salt: str = "") -> tuple[Checklist, int]:
    reply = examiner.ask("checklist", {"question": question})
    items: list[str] = []
    for it in reply.data.get("items", []) if isinstance(reply.data.get("items"), list) else []:
        if isinstance(it, str) and it.strip() and it.strip() not in items:
            items.append(it.strip())
    # Only items the feedback never touches can be held back, or the feedback would give them away.
    eligible = [s for s in items if not ABOUT_CITING.search(s)]
    n = max(1, round(len(eligible) * hold_back)) if len(eligible) >= 2 else 0
    # Chosen by fingerprint, so the writer cannot steer the split. A different salt per run
    # holds back different items, so a writer run many times cannot learn which ones are hidden.
    hidden = sorted(eligible, key=lambda s: hashlib.sha256((salt + s).encode()).hexdigest())[:n]
    visible = [s for s in items if s not in hidden]
    fp = hashlib.sha256(json.dumps([question, visible, hidden]).encode()).hexdigest()[:16]
    return Checklist(question, visible, hidden, fp), reply.tokens


@dataclass
class Score:
    metrics: dict
    claims: list[dict] = field(default_factory=list)
    failing: list[str] = field(default_factory=list)
    tokens: int = 0

    def feedback(self, terse: bool = False) -> dict:
        """What the writer is told. Only visible items; never the held-back ones.

        terse=True says that checklist points are missing without saying which. Writers given
        detailed failure lists learn to dodge checks more often (arXiv 2609.28614).
        """
        open_points = [f.split(":", 1)[1].strip(" ?") if f.startswith("Does the report answer:") else f
                       for f in self.failing]
        if terse and open_points:
            open_points = ["Some parts of the question are not answered yet."]
        return {
            "unsupported": [c["raw"] for c in self.claims if c["cites"] and not c["supported"]],
            "uncited": [c["raw"] for c in self.claims if not c["cites"]],
            "copied": [c["raw"] for c in self.claims if c["copied"]],
            "open_points": open_points,
        }

    def needs_sources(self) -> list[str]:
        """Sentences that failed their check: worth a fresh search before they are cut."""
        return [c["text"] for c in self.claims if c["cites"] and not c["supported"] and not c["over_cited"]]


def copied(claim: str, passage: str) -> bool:
    """True when a long claim is almost entirely pasted from the source, in one piece or stitched together.

    Only stretches of 20+ characters count, so ordinary shared words do not add up to a paste.
    """
    if len(claim) < 60:
        return False
    a, b = claim.lower(), passage.lower()
    blocks = difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    return sum(m.size for m in blocks if m.size >= 20) / len(a) >= 0.9


def score_report(report: str, question: str, items: list[str], examiner: Model, source: Source) -> Score:
    tokens = 0
    rows = []
    for c in claims(report):
        docs, unknown = [], 0
        for token in c.cites:
            d = source.resolve(token)
            if d is None:
                unknown += 1
            elif d not in docs:
                docs.append(d)
        over = len(c.cites) > MAX_CITES
        ok, was_copied = False, False
        if docs and not over:
            passage = "\n".join(best_passage(d.text, c.text, 2 if len(docs) > 1 else 3) for d in docs)
            was_copied = copied(c.text, passage)
            r = examiner.ask("support", {"claim": c.text, "source": passage})
            tokens += r.tokens
            ok = truthy(r.data.get("supported"))
        rows.append({"raw": c.raw, "text": c.text, "cites": c.cites, "pages": [d.id for d in docs],
                     "unknown_cites": unknown, "over_cited": over, "supported": ok, "copied": was_copied})
    failing = []
    for item in items:
        r = examiner.ask("check", {"question": question, "report": report, "item": item})
        tokens += r.tokens
        if not truthy(r.data.get("pass")):
            failing.append(item)
    n = len(rows)
    sup = sum(r["supported"] for r in rows)
    metrics = {
        "claims": n,
        "supported": sup,
        "supported_share": round(sup / n, 4) if n else 0.0,
        "uncited": sum(not r["cites"] for r in rows),
        "unknown_cites": sum(r["unknown_cites"] for r in rows),
        "over_cited": sum(r["over_cited"] for r in rows),
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
    """Average of repeated scorings. Per-sentence verdicts and failing items come from a majority vote."""
    first = scores[0]
    metrics = dict(first.metrics)
    for m in KEY_METRICS:
        metrics[m] = round(statistics.fmean(s.metrics[m] for s in scores), 4)
    rows = []
    for i, row in enumerate(first.claims):
        votes = sum(s.claims[i]["supported"] for s in scores if i < len(s.claims))
        rows.append({**row, "supported": votes * 2 > len(scores)})
    failing = [f for f in first.failing if sum(f in s.failing for s in scores) * 2 > len(scores)]
    return Score(metrics, rows, failing, sum(s.tokens for s in scores))


def accept(best: dict, cand: dict, margin: dict, first: dict | None = None) -> tuple[bool, str]:
    for ref, label in ((best, "best so far"), (first, "first draft")):
        if ref is None:
            continue
        for m in KEY_METRICS:
            if cand[m] < ref[m] - margin[m]:
                return False, f"{m} fell below the {label}: {ref[m]} to {cand[m]}"
    if cand.get("copied", 0) > best.get("copied", 0):
        return False, f"more sentences pasted from sources: {best.get('copied', 0)} to {cand['copied']}"
    gains = [m for m in GAIN_METRICS if cand[m] > best[m] + margin[m]]
    if not gains:
        return False, "no gain bigger than the noise"
    return True, "better on " + ", ".join(gains)


def key_recall(report: str, keys: list[str]) -> float:
    text = normalise(report)
    return round(sum(normalise(k) in text for k in keys) / len(keys), 4) if keys else 0.0
