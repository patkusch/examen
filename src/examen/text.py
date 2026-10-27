"""Small text helpers shared by the scorer, the sources and the offline model."""
from __future__ import annotations

import re
from dataclasses import dataclass

STOP = set(
    "a an the of in on at to for and or but is are was were be been by with from as that this it its "
    "which who whom what when where how did does do has have had there their they he she his her into "
    "than then also about over after before since many much any all each every report say answer".split()
)

# Citation styles real models drift into, all read the same way:
#   [id]  [a, b]  [a; b]  【id】  (source: id)  (sources: a, b)
CITE_PATTERNS = [
    re.compile(r"\[([^\[\]\n]{1,200})\]"),
    re.compile(r"【([^【】\n]{1,200})】"),
    re.compile(r"\((?:source|sources|src)\s*:\s*([^()\n]{1,200})\)", re.I),
]
ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "e.g.", "i.e.", "etc.", "vs.", "no.", "c.", "ca.", "jr.", "sr."}
_SPLIT = re.compile(r"(?<=[.!?])\s+")


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


def _merge_abbrev(parts: list[str]) -> list[str]:
    out: list[str] = []
    for p in parts:
        last = out[-1].split()[-1].lower() if out and out[-1].split() else ""
        if out and (last in ABBREV or re.fullmatch(r"[A-Za-z]\.", last)):
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        # Headings are text too: a made-up fact in a heading must be checked like any other.
        line = re.sub(r"^\s*#+\s*", "", line).strip()
        line = re.sub(r"^[-*]\s+|^\d+[.)]\s+", "", line)
        if not line:
            continue
        out.extend(s.strip() for s in _merge_abbrev(_SPLIT.split(line)) if s.strip())
    return out


def find_cites(sentence: str) -> list[str]:
    out = []
    for pat in CITE_PATTERNS:
        for group in pat.findall(sentence):
            out += [t.strip() for t in re.split(r"[;,]", group) if t.strip()]
    return out


def strip_cites(text: str) -> str:
    for pat in CITE_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


@dataclass
class Claim:
    raw: str          # the sentence as written, citations included
    text: str         # the sentence with citations removed
    cites: list[str]  # citation tokens as written; the scorer resolves them to pages


def claims(report: str) -> list[Claim]:
    out = []
    for s in sentences(report):
        text = strip_cites(s)
        if len(content(text)) < 2:
            continue
        out.append(Claim(raw=s, text=text, cites=find_cites(s)))
    return out


def best_passage(doc_text: str, claim: str, n: int = 3) -> str:
    """The n sentences of a source that share most words with the claim, in their original order."""
    sents = sentences(doc_text)
    ranked = sorted(range(len(sents)), key=lambda i: (-overlap(claim, sents[i]), i))[:n]
    return " ".join(sents[i] for i in sorted(ranked))


def truthy(v) -> bool:
    """Models answer true, "true", "yes"; all mean yes. Anything else is no."""
    return v is True or (isinstance(v, str) and v.strip().lower() in ("true", "yes"))
