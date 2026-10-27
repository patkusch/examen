"""Small text helpers shared by the scorer, the sources and the offline model."""
from __future__ import annotations

import re
from dataclasses import dataclass

STOP = set(
    "a an the of in on at to for and or but is are was were be been by with from as that this it its "
    "which who whom what when where how did does do has have had there their they he she his her into "
    "than then also about over after before since many much any all each every report say answer".split()
)

CITE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9_:.\-]*)\]")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def words(text: str) -> list[str]:
    return [w.strip(",'-") for w in re.findall(r"[a-z0-9][a-z0-9,'\-]*", text.lower()) if w.strip(",'-")]


def content(text: str) -> list[str]:
    return [w for w in words(text) if w not in STOP and len(w) > 1]


def overlap(a: str, b: str) -> float:
    """Share of the content words of `a` that also appear in `b`."""
    wa = content(a)
    if not wa:
        return 0.0
    wb = set(content(b))
    return sum(w in wb for w in wa) / len(wa)


def normalise(text: str) -> str:
    return " ".join(text.lower().split())


def sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*]\s+|^\d+[.)]\s+", "", line)
        out.extend(s.strip() for s in _SPLIT.split(line) if s.strip())
    return out


@dataclass
class Claim:
    raw: str          # the sentence as written, citations included
    text: str         # the sentence with citations removed
    cites: list[str]


def claims(report: str) -> list[Claim]:
    out = []
    for s in sentences(report):
        text = " ".join(CITE.sub("", s).split()).replace(" .", ".")
        if len(content(text)) < 2:
            continue
        out.append(Claim(raw=s, text=text, cites=CITE.findall(s)))
    return out


def best_passage(doc_text: str, claim: str, n: int = 3) -> str:
    """The n sentences of a source that share most words with the claim, in their original order."""
    sents = sentences(doc_text)
    ranked = sorted(range(len(sents)), key=lambda i: (-overlap(claim, sents[i]), i))[:n]
    return " ".join(sents[i] for i in sorted(ranked))
