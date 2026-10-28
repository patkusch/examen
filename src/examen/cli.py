"""examen: a research agent that checks its own work against things it cannot argue with."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .bench import bench
from .calibrate import FALSE_PASS_LIMIT, FALSE_REJECT_LIMIT, TRUST_BAR, calibrate, make_labels
from .loop import Config, run
from .models import family, load_model, model_name
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
        return (f"warning: examiner {examiner} scored {cal['accuracy']:.0%} on labelled claims, passed "
                f"{cal['false_pass_rate']:.0%} of the false ones and rejected {cal['false_reject_rate']:.0%} of the "
                f"true ones (bar: {TRUST_BAR:.0%} right, at most {FALSE_PASS_LIMIT:.0%} false passed, at most "
                f"{FALSE_REJECT_LIMIT:.0%} true rejected). Treat its verdicts as rough: the loop will cut true "
                f"sentences it wrongly rejects.")
    return None


def _print_run(r: dict) -> None:
    f = r["final"]
    if not r["held_back"]:
        print("warning: the checklist was too short to hold any questions back, so there is no hidden check",
              file=sys.stderr)
    print(f"\n{r['report']}\n")
    print(f"rounds {r['rounds']} ({r['stopped']}); writer tokens {r['agent_tokens']} of {r['budget']}, "
          f"examiner tokens {r['examiner_tokens']}")
    print(f"claims backed by their source: {f['supported']:g} of {f['claims']} ({f['supported_share']:.0%}); "
          f"no source given: {f['uncited']}")
    print(f"checklist passed: {f['visible_pass']:.0%} seen by the writer, "
          + (f"{f['hidden_pass']:.0%} held back" if f["hidden_pass"] is not None else "none held back"))
    if "key_recall" in f:
        print(f"answer key found: {f['key_recall']:.0%}")
    print("note: 'backed by its source' means the page says it, not that it is true.")


def _calibration_summary(r: dict) -> str:
    lines = [f"examiner: {r['examiner']}  ({r['pairs']} claims)",
             f"right:                     {r['accuracy']:.0%}   (needs {r['bar']['accuracy']:.0%})",
             f"false claims let through:  {r['false_pass_rate']:.0%}   (at most {r['bar']['false_pass_rate']:.0%})",
             f"  of the held-out kinds:   {r['held_out_false_pass_rate']:.0%}   (at most "
             f"{r['bar']['held_out_false_pass_rate']:.0%})",
             f"true claims rejected:      {r['false_reject_rate']:.0%}   (at most {r['bar']['false_reject_rate']:.0%})",
             f"same verdict when re-asked: {r['self_agreement']:.0%}"]
    lines += [f"  {k}: {v} let through" for k, v in r["false_pass_by_kind"].items()]
    lines += [f"  {k} true claims: {v} rejected" for k, v in r["false_reject_by_kind"].items()]
    if r.get("decided_by_code") is not None:
        lines.append(f"decided by code checks, without asking the model: {r['decided_by_code']}")
    lines.append("TRUSTED" if r["trusted"] else "NOT TRUSTED: do not use it to grade the bench")
    return "\n".join(lines)


def _show(folder: Path) -> int:
    if not (folder / "rounds.jsonl").exists():
        runs = sorted(p.parent for p in folder.glob("*/rounds.jsonl"))
        if not runs:
            print(f"no run receipts in {folder}", file=sys.stderr)
            return 1
        folder = runs[-1]
    print(f"run: {folder}")
    print(f"{'round':<7}{'kept':<6}{'backed':>8}{'no source':>11}{'checklist':>11}{'tokens':>8}  why")
    for line in (folder / "rounds.jsonl").read_text().splitlines():
        r = json.loads(line)
        m = r["metrics"]
        print(f"{r['round']:<7}{'yes' if r['kept'] else 'no':<6}{m['supported']:>4g}/{m['claims']:<3}"
              f"{m['uncited']:>11}{m['visible_pass']:>11.0%}{r['agent_tokens']:>8}  {r['why']}")
    final = folder / "final.json"
    if final.exists():
        f = json.loads(final.read_text())
        print(f"stopped: {f['stopped']}; held-back checklist passed: "
              + ("-" if f["final"]["hidden_pass"] is None else f"{f['final']['hidden_pass']:.0%}"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examen", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, writer=True):
        if writer:
            p.add_argument("--writer", default="fake", help="fake, fake-flawed, ollama:<model>, claude:<model>")
        p.add_argument("--examiner", default="fake", help="the model that grades; best from a different family")
        p.add_argument("--receipts", default="receipts", help="folder for everything the run decided")
        if writer:
            p.add_argument("--require-trusted", action="store_true",
                           help="refuse to start unless the examiner has passed `examen calibrate`")

    def loop_options(p):
        p.add_argument("--terse", action="store_true",
                       help="tell the writer only that points are missing, not which (harder to game)")
        p.add_argument("--cite-pass", action="store_true",
                       help="write without citations, then add them in a pass that may not change any words")
        p.add_argument("--split-seed", default="",
                       help="changes which checklist questions are held back; use a new one for each run")

    d = sub.add_parser("demo", help="offline run on the invented islands, with a writer that makes mistakes")
    d.add_argument("--question", default=None)
    d.add_argument("--receipts", default="receipts")

    r = sub.add_parser("run", help="research one question")
    r.add_argument("question")
    r.add_argument("--source", default="fixture", choices=["fixture", "wikipedia"])
    r.add_argument("--mode", default="team", choices=["team", "single"])
    r.add_argument("--no-loop", action="store_true")
    r.add_argument("--rounds", type=int, default=4)
    r.add_argument("--budget", type=int, default=60000)
    r.add_argument("--repeats", type=int, default=3)
    loop_options(r)
    common(r)

    b = sub.add_parser("bench", help="the four set-ups on the invented-island questions, same budget")
    b.add_argument("--budget", type=int, default=60000)
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--repeats", type=int, default=3)
    loop_options(b)
    common(b)

    c = sub.add_parser("calibrate", help="measure the examiner on claims with known answers")
    c.add_argument("--pairs", type=int, default=84)
    c.add_argument("--runs", type=int, default=2, help="times each claim is judged, each with its own seed")
    c.add_argument("--json", action="store_true", help="print the full result as JSON")
    c.add_argument("--label-seed", type=int, default=7,
                   help="draws a different set of test claims; use a new one to check a result was not fitted to one set")
    common(c, writer=False)

    sh = sub.add_parser("show", help="print what a past run decided, round by round, from its receipts")
    sh.add_argument("folder", help="a run folder (holds rounds.jsonl), or a receipts folder to show the newest run")

    lab = sub.add_parser("labels", help="write the labelled claim pairs to a file")
    lab.add_argument("out")
    lab.add_argument("--pairs", type=int, default=84)

    a = ap.parse_args(argv)

    if a.cmd == "show":
        return _show(Path(a.folder))

    if a.cmd == "labels":
        Path(a.out).write_text("\n".join(json.dumps(x) for x in make_labels(a.pairs)) + "\n")
        print(f"wrote {a.pairs} pairs to {a.out}")
        return 0

    if a.cmd == "calibrate":
        ex = load_model(a.examiner)
        res = calibrate(ex, make_labels(a.pairs, seed=a.label_seed), runs=max(1, a.runs))
        res["label_seed"] = a.label_seed
        Receipts(Path(a.receipts) / "calibration").write_json(ex.name.replace(":", "_").replace("/", "_") + ".json", res)
        print(json.dumps(res, indent=2) if a.json else _calibration_summary(res))
        return 0

    if a.cmd == "demo":
        q = load_corpus()["questions"][0]
        question = a.question or q["question"]
        print(f"question: {question}")
        print("writer: fake-flawed (adds one made-up sentence and one with no source)  examiner: fake")
        res = run(question, load_model("fake-flawed"), load_model("fake"), make_source("fixture"),
                  Config(), _receipts(a.receipts, "demo"), q["keys"] if a.question is None else None)
        _print_run(res)
        return 0

    if family(a.writer) and family(a.writer) == family(a.examiner):
        print(f"warning: writer and examiner are both {family(a.writer)} models. Models favour writing like "
              "their own, so the examiner may go easy on the writer. Use a different family if you can.",
              file=sys.stderr)
    note = _trust_note(a.examiner, a.receipts)
    if note:
        print(note, file=sys.stderr)
        if a.require_trusted:
            print("stopped: --require-trusted is set and the examiner has not passed its test", file=sys.stderr)
            return 2

    if a.cmd == "run":
        cfg = Config(mode=a.mode, loop=not a.no_loop, max_rounds=a.rounds, budget=a.budget, repeats=a.repeats,
                     terse=a.terse, cite_pass=a.cite_pass, split_seed=a.split_seed)
        res = run(a.question, load_model(a.writer), load_model(a.examiner), make_source(a.source), cfg,
                  _receipts(a.receipts, "run"))
        _print_run(res)
        return 0

    if a.cmd == "bench":
        res = bench(load_model(a.writer), load_model(a.examiner), a.budget, a.limit,
                    _receipts(a.receipts, "bench"), a.repeats, terse=a.terse, cite_pass=a.cite_pass)
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
