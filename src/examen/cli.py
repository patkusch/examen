"""examen: a research agent that checks its own work against things it cannot argue with."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .bench import bench
from .calibrate import FALSE_PASS_LIMIT, TRUST_BAR, calibrate, make_labels
from .loop import Config, run
from .models import load_model, model_name
from .receipts import Receipts
from .sources import load_corpus, make_source


def _receipts(base: str, name: str) -> Receipts:
    return Receipts(Path(base) / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}")


def _trust_note(examiner: str, receipts_dir: str) -> str | None:
    """Warn when the examiner has never been measured, or was measured and fell short."""
    examiner = model_name(examiner)
    path = Path(receipts_dir) / "calibration" / (examiner.replace(":", "_").replace("/", "_") + ".json")
    if not path.exists():
        return f"warning: examiner {examiner} has not been measured. Run: examen calibrate --examiner {examiner}"
    cal = json.loads(path.read_text())
    if not cal["trusted"]:
        return (f"warning: examiner {examiner} scored {cal['accuracy']:.0%} on labelled claims and passed "
                f"{cal['false_pass_rate']:.0%} of the false ones (bar: {TRUST_BAR:.0%} right, at most "
                f"{FALSE_PASS_LIMIT:.0%} false passed). Treat its verdicts as rough.")
    return None


def _print_run(r: dict) -> None:
    f = r["final"]
    print(f"\n{r['report']}\n")
    print(f"rounds {r['rounds']} ({r['stopped']}); writer tokens {r['agent_tokens']}, examiner tokens {r['examiner_tokens']}")
    print(f"claims backed by their source: {f['supported']:g} of {f['claims']} ({f['supported_share']:.0%}); "
          f"no source given: {f['uncited']}")
    print(f"checklist passed: {f['visible_pass']:.0%} seen by the writer, "
          + (f"{f['hidden_pass']:.0%} held back" if f["hidden_pass"] is not None else "none held back"))
    if "key_recall" in f:
        print(f"answer key found: {f['key_recall']:.0%}")
    print("note: 'backed by its source' means the page says it, not that it is true.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examen", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, writer=True):
        if writer:
            p.add_argument("--writer", default="fake", help="fake, fake-flawed, ollama:<model>, claude:<model>")
        p.add_argument("--examiner", default="fake", help="the model that grades; best from a different family")
        p.add_argument("--receipts", default="receipts", help="folder for everything the run decided")

    d = sub.add_parser("demo", help="offline run on the invented islands, with a writer that makes mistakes")
    d.add_argument("--question", default=None)

    r = sub.add_parser("run", help="research one question")
    r.add_argument("question")
    r.add_argument("--source", default="fixture", choices=["fixture", "wikipedia"])
    r.add_argument("--mode", default="team", choices=["team", "single"])
    r.add_argument("--no-loop", action="store_true")
    r.add_argument("--rounds", type=int, default=4)
    r.add_argument("--budget", type=int, default=60000)
    r.add_argument("--repeats", type=int, default=3)
    common(r)

    b = sub.add_parser("bench", help="the four set-ups on the invented-island questions, same budget")
    b.add_argument("--budget", type=int, default=60000)
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--repeats", type=int, default=3)
    common(b)

    c = sub.add_parser("calibrate", help="measure the examiner on claims with known answers")
    c.add_argument("--pairs", type=int, default=60)
    common(c, writer=False)

    lab = sub.add_parser("labels", help="write the labelled claim pairs to a file")
    lab.add_argument("out")
    lab.add_argument("--pairs", type=int, default=60)

    a = ap.parse_args(argv)

    if a.cmd == "labels":
        Path(a.out).write_text("\n".join(json.dumps(x) for x in make_labels(a.pairs)) + "\n")
        print(f"wrote {a.pairs} pairs to {a.out}")
        return 0

    if a.cmd == "calibrate":
        ex = load_model(a.examiner)
        res = calibrate(ex, make_labels(a.pairs))
        Receipts(Path(a.receipts) / "calibration").write_json(ex.name.replace(":", "_").replace("/", "_") + ".json", res)
        print(json.dumps(res, indent=2))
        return 0

    if a.cmd == "demo":
        q = load_corpus()["questions"][0]
        question = a.question or q["question"]
        print(f"question: {question}")
        print("writer: fake-flawed (adds one made-up sentence and one with no source)  examiner: fake")
        res = run(question, load_model("fake-flawed"), load_model("fake"), make_source("fixture"),
                  Config(), _receipts("receipts", "demo"), q["keys"] if a.question is None else None)
        _print_run(res)
        return 0

    note = _trust_note(a.examiner, a.receipts)
    if note:
        print(note, file=sys.stderr)

    if a.cmd == "run":
        cfg = Config(mode=a.mode, loop=not a.no_loop, max_rounds=a.rounds, budget=a.budget, repeats=a.repeats)
        res = run(a.question, load_model(a.writer), load_model(a.examiner), make_source(a.source), cfg,
                  _receipts(a.receipts, "run"))
        _print_run(res)
        return 0

    if a.cmd == "bench":
        res = bench(load_model(a.writer), load_model(a.examiner), a.budget, a.limit,
                    _receipts(a.receipts, "bench"), a.repeats)
        print(f"{'set-up':<14}{'correct':>9}{'key found':>11}{'backed':>8}{'held-back':>11}{'tokens':>9}")
        for arm, s in res["summary"].items():
            hp = "-" if s["hidden_pass"] is None else f"{s['hidden_pass']:.0%}"
            print(f"{arm:<14}{s['correct']:>5}/{s['of']:<3}{s['key_recall']:>11.0%}{s['supported_share']:>8.0%}"
                  f"{hp:>11}{s['agent_tokens']:>9}")
        for k, v in res["paired"].items():
            print(f"{k}: better on {v['wins']}, worse on {v['losses']}, same on {v['ties']}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
