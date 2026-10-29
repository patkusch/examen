"""Checks done by code before the examiner model is asked, and examiners built from other examiners.

The code checks can only say no. A claim whose numbers, names or "not" do not match the page is
rejected without asking the model; anything else still goes to the model. They were built for the
targeted kinds in calibrate.py, which is why calibration also has held-out kinds they never saw.
"""
from __future__ import annotations

import re

from .models import Model, Reply
from .text import normalise, truthy, words

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
CAPS = re.compile(r"\b[A-Z][a-zA-Z'\-]+")
NEG = re.compile(r"\b(not|never|no|none|nobody|nothing|neither|nor)\b|n't\b", re.I)
COMMON_CAPS = {"The", "A", "An", "It", "Its", "He", "She", "His", "Her", "They", "Their", "This", "That", "These",
               "Those", "There", "In", "On", "At", "By", "For", "From", "After", "Before", "Since", "As", "And",
               "But", "Or", "Today", "Most", "Some", "Many", "Besides", "Both", "Each", "One", "When", "While",
               # Ordinary words that start sentences. "According" here once vetoed every true claim that
               # began "According to the ... page," (found 2026-10-29).
               "According", "However", "Also", "Currently", "Although", "Because", "During", "Over", "Under",
               "Every", "Several", "About", "Around", "Only", "Unlike", "Like", "Despite", "Following", "Later",
               "Earlier", "Until", "Within", "Without", "Yet", "So", "Then", "Now", "Here", "Our", "We", "You"}


def veto(claim: str, passage: str) -> str | None:
    """Why the claim cannot be supported by the passage, or None if code has no objection."""
    nums = {n.replace(",", "").rstrip(".") for n in NUM.findall(claim)}
    have = {n.replace(",", "").rstrip(".") for n in NUM.findall(passage)}
    if nums - have:
        return "number not on the page: " + ", ".join(sorted(nums - have))
    # Compared ignoring case: "About" at the start of a sentence is the page's "about", not a name.
    words = {re.sub(r"'s$", "", w.lower()) for w in re.findall(r"[A-Za-z'\-]+", passage)}
    # "Seld's" is the page's "Seld": compare names without a possessive ending.
    caps = {re.sub(r"'s$", "", w) for w in CAPS.findall(claim)}
    missing = sorted({w for w in caps if w not in COMMON_CAPS and w.lower() not in words})
    if missing:
        return "name not on the page: " + ", ".join(missing)
    if NEG.search(claim) and not NEG.search(passage):
        return "the claim says not; the page does not"
    return None


class Guarded(Model):
    """An examiner with the code checks in front of it."""

    def __init__(self, inner: Model) -> None:
        self.inner = inner
        self.name = "guarded:" + inner.name
        self.vetoes = 0

    @property
    def served(self) -> set:
        return getattr(self.inner, "served", set())

    def vary(self, i: int) -> "Guarded":
        return Guarded(self.inner.vary(i)) if i else self

    def ask(self, role: str, payload: dict) -> Reply:
        if role == "support":
            reason = veto(payload["claim"], payload["source"])
            if reason:
                self.vetoes += 1
                return Reply({"supported": False, "vetoed": reason}, 0)
        return self.inner.ask(role, payload)


class Panel(Model):
    """Several examiners; a claim is backed, or a checklist item passed, only if every one says yes.

    Different models miss different things (gemma3 4B misses made-up details, 12B misses an added
    "not"), so requiring all of them cuts what slips through. Asking stops at the first no.
    """

    def __init__(self, members: list[Model]) -> None:
        self.members = members
        self.name = "panel:" + "+".join(m.name for m in members)

    @property
    def served(self) -> set:
        return set().union(*(getattr(m, "served", set()) for m in self.members))

    def vary(self, i: int) -> "Panel":
        return Panel([m.vary(i) for m in self.members]) if i else self

    def ask(self, role: str, payload: dict) -> Reply:
        if role not in ("support", "check"):
            return self.members[0].ask(role, payload)
        key = "supported" if role == "support" else "pass"
        tokens = 0
        for m in self.members:
            r = m.ask(role, payload)
            tokens += r.tokens
            if not truthy(r.data.get(key)):
                return Reply({key: False}, tokens)
        return Reply({key: True}, tokens)


class QuoteFirst(Model):
    """An examiner that has to show its evidence before it answers.

    Step 1: it copies the sentence from the passage closest to stating the claim.
    Step 2: code checks the quote really is in the passage and is a real sentence; if not, no.
    Step 3: in a separate short question it splits the claim into facts and says, for each, whether
            the quote states it. Code backs the claim only if every fact is in the quote, so a claim
            that says less than the page passes and one that says something else fails.
    The comparison sees one sentence instead of a whole passage, so small differences have
    nowhere to hide. Judges that cite evidence before scoring are reported to be more reliable.
    """

    def __init__(self, inner: Model) -> None:
        self.inner = inner
        self.name = "quote:" + inner.name
        self.bad_quotes = 0

    @property
    def served(self) -> set:
        return getattr(self.inner, "served", set())

    def vary(self, i: int) -> "QuoteFirst":
        return QuoteFirst(self.inner.vary(i)) if i else self

    def ask(self, role: str, payload: dict) -> Reply:
        if role != "support":
            return self.inner.ask(role, payload)
        q = self.inner.ask("quote", {"claim": payload["claim"], "source": payload["source"]})
        quote = str(q.data.get("quote") or "").strip()
        if len(words(quote)) < 3 or normalise(quote) not in normalise(payload["source"]):
            self.bad_quotes += 1
            return Reply({"supported": False, "why": "no exact quote from the page"}, q.tokens)
        c = self.inner.ask("compare", {"claim": payload["claim"], "quote": quote})
        facts = c.data.get("facts")
        if isinstance(facts, list) and facts:
            # The model splits the claim into facts; code decides: backed only if every fact is in the quote.
            ok = all(isinstance(f, dict) and truthy(f.get("in_quote")) for f in facts)
        else:
            ok = truthy(c.data.get("same"))
        return Reply({"supported": ok, "quote": quote, "facts": facts}, q.tokens + c.tokens)
