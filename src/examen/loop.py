"""One research run: draft, score, improve, keep only real gains, stop when the outside numbers stall.

Two shapes, so they can be compared at the same budget:
- team: a planner splits the question, read-only researchers each take one piece with a fresh
  context and return short quoted notes, and one writer turns the notes into the report.
- single: one agent reads the search results and writes the report itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Model
from .receipts import Receipts
from .score import Checklist, Score, accept, key_recall, make_checklist, mean_score, noise, score_report
from .sources import Source, doc_dict
from .text import normalise


@dataclass
class Config:
    mode: str = "team"        # team | single
    loop: bool = True
    max_rounds: int = 4
    patience: int = 2         # rounds in a row without a kept improvement before stopping
    budget: int = 60000       # tokens the writer side may spend (examiner tokens are counted apart)
    repeats: int = 3          # times the first draft is scored, to measure noise
    k_docs: int = 4
    max_quote: int = 400


class Run:
    def __init__(self, question: str, writer: Model, examiner: Model, source: Source, cfg: Config,
                 receipts: Receipts | None = None, keys: list[str] | None = None) -> None:
        self.q, self.writer, self.examiner, self.source, self.cfg = question, writer, examiner, source, cfg
        self.receipts = receipts or Receipts(None)
        self.keys = keys or []
        self.agent_tokens = 0
        self.examiner_tokens = 0
        self.notes: list[dict] = []
        self.dropped_quotes = 0
        self.seen_by_writer: list[dict] = []  # every payload the writer side received, for the leak test

    # ------------------------------------------------------------ writer side

    def _ask(self, role: str, payload: dict) -> dict:
        self.seen_by_writer.append({"role": role, "payload": payload})
        r = self.writer.ask(role, payload)
        self.agent_tokens += r.tokens
        return r.data

    def _research(self, topic: str) -> list[dict]:
        docs = self.source.search(topic, self.cfg.k_docs)
        data = self._ask("notes", {"subquestion": topic, "docs": [doc_dict(d) for d in docs]})
        good = []
        for n in data.get("notes", []) if isinstance(data.get("notes"), list) else []:
            if not isinstance(n, dict):
                continue
            doc = self.source.get(str(n.get("source", "")))
            quote = str(n.get("quote", ""))[: self.cfg.max_quote]
            # A note survives only if its quote really is in the page it names.
            if doc and quote and normalise(quote) in normalise(doc.text):
                good.append({"source": doc.id, "quote": quote, "point": str(n.get("point") or quote)})
            else:
                self.dropped_quotes += 1
        return good

    def _draft(self, previous: str = "", feedback: dict | None = None) -> str:
        feedback = feedback or {}
        if self.cfg.mode == "single":
            topics = feedback.get("open_points") or [self.q]
            docs = {}
            for t in topics[:3]:
                for d in self.source.search(t, self.cfg.k_docs):
                    docs[d.id] = doc_dict(d)
            data = self._ask("write_from_docs", {"question": self.q, "docs": list(docs.values()),
                                                 "previous_report": previous, "feedback": feedback})
            return str(data.get("report", ""))
        gaps = feedback.get("open_points", [])
        plan = self._ask("plan", {"question": self.q, "gaps": gaps})
        subs = [s for s in plan.get("subquestions", []) if isinstance(s, str)][:4] or [self.q]
        for s in subs:
            for n in self._research(s):
                if n not in self.notes:
                    self.notes.append(n)
        data = self._ask("write", {"question": self.q, "notes": self.notes,
                                   "previous_report": previous, "feedback": feedback})
        return str(data.get("report", ""))

    # ------------------------------------------------------------ examiner side

    def _score(self, report: str, items: list[str], repeats: int = 1) -> list[Score]:
        out = [score_report(report, self.q, items, self.examiner, self.source) for _ in range(repeats)]
        self.examiner_tokens += sum(s.tokens for s in out)
        return out

    # ------------------------------------------------------------ the run

    def go(self) -> dict:
        checklist, t = make_checklist(self.examiner, self.q)
        self.examiner_tokens += t
        self.receipts.write_json("checklist.json", checklist.to_dict())

        report = self._draft()
        first = self._score(report, checklist.visible, self.cfg.repeats)
        margin = noise(first)
        best, best_report = mean_score(first), report
        self._log(1, report, best, True, "first draft", margin)

        stop, stale, rnd = "one round only", 0, 1
        while self.cfg.loop:
            if rnd >= self.cfg.max_rounds:
                stop = "round limit"
                break
            if self.agent_tokens >= self.cfg.budget:
                stop = "budget spent"
                break
            fb = best.feedback()
            if not any(fb.values()):
                stop = "nothing left to fix"
                break
            rnd += 1
            cand_report = self._draft(best_report, fb)
            cand = self._score(cand_report, checklist.visible)[0]
            ok, why = accept(best.metrics, cand.metrics, margin)
            self._log(rnd, cand_report, cand, ok, why, margin)
            if ok:
                best, best_report, stale = cand, cand_report, 0
            else:
                stale += 1
                if stale >= self.cfg.patience:
                    stop = f"no kept gain in {stale} rounds"
                    break

        final = self._final(best_report, checklist)
        result = {
            "question": self.q, "mode": self.cfg.mode, "loop": self.cfg.loop, "rounds": rnd, "stopped": stop,
            "writer": self.writer.name, "examiner": self.examiner.name, "source": self.source.name,
            "agent_tokens": self.agent_tokens, "examiner_tokens": self.examiner_tokens,
            "dropped_quotes": self.dropped_quotes, "noise": margin, "checklist": checklist.fingerprint,
            "final": final, "report": best_report,
        }
        self.receipts.write_json("final.json", result)
        self.receipts.write_text("report.md", best_report + "\n")
        return result

    def _final(self, report: str, checklist: Checklist) -> dict:
        """A fresh scoring that took no part in choosing the version, plus the held-back items."""
        fresh = mean_score(self._score(report, checklist.visible, self.cfg.repeats))
        hidden = self._score(report, checklist.hidden)[0] if checklist.hidden else None
        out = dict(fresh.metrics)
        out["hidden_pass"] = hidden.metrics["visible_pass"] if hidden else None
        if self.keys:
            out["key_recall"] = key_recall(report, self.keys)
            out["correct"] = out["key_recall"] == 1.0
        return out

    def _log(self, rnd: int, report: str, s: Score, kept: bool, why: str, margin: dict) -> None:
        self.receipts.append("rounds.jsonl", {
            "round": rnd, "kept": kept, "why": why, "metrics": s.metrics, "failing": s.failing,
            "claims": s.claims, "noise": margin, "agent_tokens": self.agent_tokens,
            "examiner_tokens": self.examiner_tokens, "report": report,
        })


def run(question: str, writer: Model, examiner: Model, source: Source, cfg: Config | None = None,
        receipts: Receipts | None = None, keys: list[str] | None = None) -> dict:
    return Run(question, writer, examiner, source, cfg or Config(), receipts, keys).go()

