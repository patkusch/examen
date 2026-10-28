"""The fair test: four set-ups on the same questions at the same token cap.

            no loop        loop
  single    one agent      one agent that revises
  team      helpers        helpers + revises

Changing two things at once proves nothing, so each of the two ideas gets its own column.
Every arm has the same token cap, checked before each call; what each arm actually spent is
reported next to its results, because the cap is a ceiling, not a target.
Correctness is checked against an answer key, not against what the report cited.
"""
from __future__ import annotations

import statistics

from .loop import Config, run
from .models import Model
from .receipts import Receipts
from .sources import FixtureSource, load_corpus

ARMS = [("single", False), ("single", True), ("team", False), ("team", True)]


def bench(writer: Model, examiner: Model, budget: int = 60000, limit: int | None = None,
          receipts: Receipts | None = None, repeats: int = 3, terse: bool = False, cite_pass: bool = False) -> dict:
    receipts = receipts or Receipts(None)
    questions = load_corpus()["questions"][:limit]
    # Rows already in this folder are kept, so a stopped run carries on where it left off.
    rows = receipts.read_rows("bench.jsonl")
    done = {(r["question"], r["arm"]) for r in rows}
    for q in questions:
        for mode, loop in ARMS:
            arm = f"{mode}{'+loop' if loop else ''}"
            if (q["id"], arm) in done:
                continue
            cfg = Config(mode=mode, loop=loop, budget=budget, repeats=repeats, terse=terse, cite_pass=cite_pass)
            sub = receipts.sub(f"{q['id']}-{arm}")
            if sub.dir and (sub.dir / "rounds.jsonl").exists():
                (sub.dir / "rounds.jsonl").unlink()  # a run cut off half way starts its log afresh
            r = run(q["question"], writer, examiner, FixtureSource(), cfg, sub, q["keys"])
            f = r["final"]
            row = {"question": q["id"], "arm": arm, "correct": f["correct"], "key_recall": f["key_recall"],
                   "supported": f["supported"], "supported_share": f["supported_share"],
                   "hidden_pass": f["hidden_pass"], "agent_tokens": r["agent_tokens"], "rounds": r["rounds"]}
            rows.append(row)
            receipts.append("bench.jsonl", row)
    summary = {}
    for mode, loop in ARMS:
        arm = f"{mode}{'+loop' if loop else ''}"
        rs = [r for r in rows if r["arm"] == arm]
        summary[arm] = {
            "correct": sum(r["correct"] for r in rs), "of": len(rs),
            "key_recall": round(statistics.fmean(r["key_recall"] for r in rs), 3),
            "supported_share": round(statistics.fmean(r["supported_share"] for r in rs), 3),
            "hidden_pass": _mean([r["hidden_pass"] for r in rs]),
            "agent_tokens": round(statistics.fmean(r["agent_tokens"] for r in rs)),
        }
    out = {"writer": writer.name, "examiner": examiner.name, "budget": budget, "summary": summary,
           "paired": {"single: loop vs no loop": _paired(rows, "single", "single+loop"),
                      "team: loop vs no loop": _paired(rows, "team", "team+loop"),
                      "no loop: team vs single": _paired(rows, "single", "team"),
                      "loop: team vs single": _paired(rows, "single+loop", "team+loop")},
           "rows": rows}
    receipts.write_json("bench.json", out)
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 3) if xs else None


def _paired(rows, a, b):
    """Per question: did arm b find more of the answer than arm a, fewer, or the same?"""
    by = {(r["question"], r["arm"]): r["key_recall"] for r in rows}
    qs = sorted({r["question"] for r in rows})
    wins = sum(by[(q, b)] > by[(q, a)] for q in qs)
    losses = sum(by[(q, b)] < by[(q, a)] for q in qs)
    return {"wins": wins, "losses": losses, "ties": len(qs) - wins - losses}
