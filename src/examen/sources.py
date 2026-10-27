"""Where the research comes from. Every page that is read is kept, so the scorer checks
claims against the exact text the agent saw, even if the live page changes later."""
from __future__ import annotations

import hashlib
import json
import math
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path

from .text import content


@dataclass
class Doc:
    id: str
    title: str
    text: str
    url: str = ""


class Source:
    name = "source"

    def __init__(self) -> None:
        self.seen: dict[str, Doc] = {}

    def search(self, query: str, k: int = 4) -> list[Doc]:
        docs = self._search(query, k)
        for d in docs:
            self.seen[d.id] = d
        return docs

    def get(self, doc_id: str) -> Doc | None:
        return self.seen.get(doc_id)

    def resolve(self, token: str) -> Doc | None:
        """A citation may name a page by id or by title; only pages fetched in this run count."""
        doc = self.seen.get(token)
        if doc:
            return doc
        t = token.strip().lower()
        return next((d for d in self.seen.values() if d.title.lower() == t), None)

    def _search(self, query: str, k: int) -> list[Doc]:
        raise NotImplementedError


def load_corpus() -> dict:
    return json.loads(resources.files("examen").joinpath("data/corpus.json").read_text())


class FixtureSource(Source):
    """The invented Brenna Isles corpus, searched with BM25. Works offline."""

    name = "fixture"

    def __init__(self, corpus: dict | None = None, preload: bool = False) -> None:
        super().__init__()
        corpus = corpus or load_corpus()
        self.docs = [Doc(d["id"], d["title"], d["text"], f"fixture://{d['id']}") for d in corpus["docs"]]
        self.tokens = [content(d.title + " " + d.text) for d in self.docs]
        self.avg = sum(map(len, self.tokens)) / len(self.tokens)
        df = Counter(w for toks in self.tokens for w in set(toks))
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        # Normally a page can only be cited once it has been found by a search in this run.
        # `preload` opens every page at once, for tests and calibration.
        if preload:
            self.seen = {d.id: d for d in self.docs}

    def _search(self, query: str, k: int) -> list[Doc]:
        q = content(query)
        scores = []
        for i, toks in enumerate(self.tokens):
            tf = Counter(toks)
            s = sum(
                self.idf.get(w, 0) * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(toks) / self.avg))
                for w in q if w in tf
            )
            scores.append((s, i))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [self.docs[i] for s, i in scores[:k] if s > 0]


class WikipediaSource(Source):
    """English Wikipedia through its public API. No key needed. Pages are cached on disk."""

    name = "wikipedia"
    API = "https://en.wikipedia.org/w/api.php"
    AGENT = "examen/0.2 (https://github.com/patkusch/examen)"
    MAX_CHARS = 8000  # long articles are cut; the writer and the examiner both see the same cut text

    def __init__(self, cache_dir: str | Path = ".examen-cache", opener=None) -> None:
        super().__init__()
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.open = opener or self._open

    def _open(self, params: dict) -> dict:
        url = self.API + "?" + urllib.parse.urlencode({**params, "format": "json"})
        req = urllib.request.Request(url, headers={"User-Agent": self.AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _cached(self, key: str, params: dict) -> dict:
        path = self.cache / (hashlib.sha256(key.encode()).hexdigest()[:24] + ".json")
        if path.exists():
            return json.loads(path.read_text())
        data = self.open(params)
        path.write_text(json.dumps(data))
        return data

    def _search(self, query: str, k: int) -> list[Doc]:
        hits = self._cached(f"s:{k}:{query}", {"action": "query", "list": "search", "srsearch": query, "srlimit": k})
        ids = [str(h["pageid"]) for h in hits.get("query", {}).get("search", [])]
        out = []
        for pid in ids:
            # One page per request: the API returns full text for only one page at a time.
            page = self._cached("p:" + pid, {"action": "query", "prop": "extracts", "explaintext": 1, "pageids": pid})
            p = page.get("query", {}).get("pages", {}).get(pid)
            if p and p.get("extract"):
                out.append(Doc(f"w{pid}", p["title"], p["extract"][: self.MAX_CHARS],
                               "https://en.wikipedia.org/?curid=" + pid))
        return out


def make_source(name: str, cache_dir: str = ".examen-cache") -> Source:
    if name == "fixture":
        return FixtureSource()
    if name == "wikipedia":
        return WikipediaSource(cache_dir)
    raise SystemExit(f"unknown source {name!r}: use fixture or wikipedia")


def doc_dict(d: Doc) -> dict:
    return asdict(d)
