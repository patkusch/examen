"""The models that play each role.

`fake` is a plain rule-based stand-in so everything runs offline and the tests are repeatable.
It is not clever and it is not meant to be: it copies sentences that share words with the
question. `fake-flawed` also slips in one made-up sentence and one sentence with no source, so
the loop has something real to catch. `ollama:<model>` and `claude:<model>` are the real ones.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass

from .prompts import parse_json, render
from .text import claims, content, overlap, sentences


@dataclass
class Reply:
    data: dict
    tokens: int


class Model:
    name = "model"

    def ask(self, role: str, payload: dict) -> Reply:
        raise NotImplementedError


# ---------------------------------------------------------------- offline stand-in

CLAUSE = re.compile(
    r",\s*(?:and\s+)?|\s+and\s+(?=(?:in|what|which|who|whom|how|where|when|under)\b)", re.I
)
PLANTED = "Experts widely agree this is the single most important fact about the subject [{src}]."
UNCITED = "Many people find this topic fascinating and keep coming back to it."
SOURCE_ITEM = "Does the report give a source for every factual sentence?"


def clauses(question: str) -> list[str]:
    parts = [p.strip(" ?") for p in CLAUSE.split(question.strip())]
    return [p for p in parts if len(content(p)) >= 2]


class FakeModel(Model):
    def __init__(self, flawed: bool = False) -> None:
        self.flawed = flawed
        self.name = "fake-flawed" if flawed else "fake"

    def ask(self, role: str, payload: dict) -> Reply:
        data = getattr(self, "_" + role)(payload)
        tokens = (len(json.dumps(payload)) + len(json.dumps(data))) // 4
        return Reply(data, tokens)

    def _checklist(self, p):
        items = [f"Does the report answer: {c}?" for c in clauses(p["question"])]
        return {"items": items + [SOURCE_ITEM]}

    def _plan(self, p):
        gaps = p.get("gaps") or []
        return {"subquestions": gaps[:3] if gaps else clauses(p["question"])}

    def _notes(self, p):
        q = p["subquestion"]
        cand = []
        for d in p["docs"]:
            for i, s in enumerate(sentences(d["text"])):
                score = overlap(q, s)
                if score > 0:
                    cand.append((-score, len(cand), d["id"], s))
        cand.sort()
        return {"notes": [{"source": src, "quote": s, "point": s} for _, _, src, s in cand[:3]]}

    def _write(self, p):
        fb = p.get("feedback") or {}
        drop = set(fb.get("unsupported", [])) | set(fb.get("uncited", []))
        if p.get("previous_report"):
            keep = [c.raw for c in claims(p["previous_report"]) if c.raw not in drop]
        else:
            keep = []
            if self.flawed and p["notes"]:
                keep = [PLANTED.format(src=p["notes"][0]["source"]), UNCITED]
        for n in p["notes"]:
            line = n["point"].rstrip(". ") + f" [{n['source']}]."
            if line not in keep:
                keep.append(line)
        paras = [" ".join(keep[i:i + 3]) for i in range(0, len(keep), 3)]
        return {"report": "\n\n".join(paras)}

    def _write_from_docs(self, p):
        topics = (p.get("feedback") or {}).get("open_points") or clauses(p["question"])
        notes = []
        for t in topics:
            notes += self._notes({"subquestion": t, "docs": p["docs"]})["notes"]
        return self._write({**p, "notes": notes})

    def _support(self, p):
        # Word overlap, plus every number in the claim must be in the source. It still misses
        # swapped names, so `examen calibrate` marks it as not to be trusted.
        nums = re.findall(r"\d[\d,]*", p["claim"])
        if any(n not in p["source"] for n in nums):
            return {"supported": False}
        best = max((overlap(p["claim"], s) for s in sentences(p["source"])), default=0.0)
        return {"supported": best >= 0.7}

    def _check(self, p):
        item, report = p["item"], p["report"]
        if item == SOURCE_ITEM:
            return {"pass": all(c.cites for c in claims(report))}
        target = item.split(":", 1)[1] if item.startswith("Does the report answer:") else item
        return {"pass": overlap(target, report) >= 0.5}


# ---------------------------------------------------------------- real models

class LLM(Model):
    def complete(self, system: str, user: str) -> tuple[str, int]:
        raise NotImplementedError

    def ask(self, role: str, payload: dict) -> Reply:
        system, user = render(role, payload)
        text, tokens = self.complete(system, user)
        data = parse_json(text)
        if not data:  # one retry with a firmer reminder; small models drift out of JSON
            text, more = self.complete(system, user + "\n\nReply with one JSON object only.")
            tokens += more
            data = parse_json(text)
        return Reply(data, tokens)


class OllamaModel(LLM):
    def __init__(self, model: str, host: str | None = None, temperature: float = 0.2, seed: int = 7,
                 timeout: float = 300) -> None:
        self.model, self.temperature, self.seed, self.timeout = model, temperature, seed, timeout
        self.host = (host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        self.name = "ollama:" + model

    def complete(self, system: str, user: str) -> tuple[str, int]:
        body = {
            "model": self.model, "stream": False, "format": "json",
            "options": {"temperature": self.temperature, "seed": self.seed},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        req = urllib.request.Request(self.host + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(r.read())
        return out["message"]["content"], out.get("prompt_eval_count", 0) + out.get("eval_count", 0)


FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class ClaudeModel(LLM):
    """Claude through the official SDK (`pip install examen[claude]`). Reads credentials the usual way."""

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low") -> None:
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - depends on the machine
            raise SystemExit("the Claude backend needs the SDK: pip install 'examen[claude]'") from e
        self.client = anthropic.Anthropic()
        self.model, self.effort = model, effort
        self.name = "claude:" + model

    def complete(self, system: str, user: str) -> tuple[str, int]:
        extra = {}
        if self.model in FALLBACK_MODELS:
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        msg = self.client.beta.messages.create(
            model=self.model, max_tokens=16000, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort}, **extra,
        )
        if msg.stop_reason == "refusal":
            return "{}", msg.usage.input_tokens + msg.usage.output_tokens
        text = "".join(b.text for b in msg.content if b.type == "text")
        return text, msg.usage.input_tokens + msg.usage.output_tokens


def model_name(spec: str) -> str:
    """The name a spec will run under, without loading it (so no SDK or server is needed)."""
    return "claude:claude-opus-5-5" if spec == "claude" else spec


def load_model(spec: str) -> Model:
    if spec in ("fake", "fake-flawed"):
        return FakeModel(flawed=spec == "fake-flawed")
    kind, _, name = spec.partition(":")
    if kind == "ollama" and name:
        return OllamaModel(name)
    if kind == "claude":
        return ClaudeModel(name or "claude-opus-5-5")
    raise SystemExit(f"unknown model {spec!r}: use fake, fake-flawed, ollama:<model> or claude:<model>")
