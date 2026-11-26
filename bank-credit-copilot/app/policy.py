"""Policy knowledge base: split the Markdown policy into clauses and search them.

Retrieval is BM25 over accent-free tokens, implemented here in ~40 lines so the demo
runs with no vector database. In a bank deployment this class is the place to swap in
Qdrant/pgvector with a Vietnamese embedding model; the rest of the pipeline only needs
`search()` and `get()`.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .textutil import norm, tokens

STOPWORDS = {
    "va", "cua", "cac", "la", "co", "duoc", "cho", "khi", "theo", "tai", "voi", "trong",
    "mot", "nhung", "thi", "de", "tu", "den", "khong", "phai", "bang", "hoac", "neu", "nay",
    # question words and generic qualifiers that appear in many clauses
    "bao", "nhieu", "gi", "nao", "the", "toi", "da", "muon", "can", "minh", "a", "oi",
}

# Tiny domain synonym list: lexical search cannot know that "thâm niên" means
# "thời gian công tác". A vector/embedding retriever removes the need for this list.
SYNONYMS = {
    "tham nien": "thoi gian cong tac",
    "lam viec": "cong tac",
    "het han": "hieu luc",
    "can cuoc": "cccd",
    "giay to": "ho so",
    "tra gop": "tra no",
    "no hien tai": "nghia vu tra no",
}


@dataclass
class Clause:
    clause_id: str      # e.g. "5.3" or "Điều 2"
    article: str        # e.g. "Điều 5. Điều kiện về khoản vay"
    text: str

    def to_dict(self) -> dict:
        return {"clause_id": self.clause_id, "article": self.article, "text": self.text}


class PolicyIndex:
    def __init__(self, path: Path):
        self.path = path
        raw = path.read_text(encoding="utf-8")
        version = re.search(r"Phiên bản:\s*([^\s—]+)", raw)
        self.version = version.group(1) if version else "unknown"
        self.clauses = self._parse(raw)
        self._docs = [[t for t in tokens(f"{c.article} {c.text}") if t not in STOPWORDS]
                      for c in self.clauses]
        self._avg_len = sum(map(len, self._docs)) / max(len(self._docs), 1)
        df = Counter(t for doc in self._docs for t in set(doc))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @staticmethod
    def _parse(raw: str) -> list[Clause]:
        clauses: list[Clause] = []
        article = ""
        buffer: list[str] = []

        def flush() -> None:
            text = " ".join(buffer).strip()
            if article and text:
                number = re.match(r"Điều (\d+)", article)
                clauses.append(Clause(f"Điều {number.group(1)}" if number else article, article, text))
            buffer.clear()

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                flush()
                article = stripped[3:].strip()
            elif re.match(r"^\d+\.\d+\.\s", stripped):
                flush()
                clause_id, text = stripped.split(" ", 1)
                clauses.append(Clause(clause_id.rstrip("."), article, text.strip()))
            elif stripped and article and not stripped.startswith(">"):
                buffer.append(stripped)
        flush()
        return clauses

    def coverage(self, query: str, clause: Clause) -> float:
        """Share of query terms found in the clause; used to refuse off-topic questions."""
        terms = self.query_terms(query)
        if not terms:
            return 0.0
        words = set(tokens(f"{clause.article} {clause.text}"))
        return sum(t in words for t in terms) / len(terms)

    def get(self, clause_id: str) -> Clause | None:
        return next((c for c in self.clauses if c.clause_id == clause_id), None)

    def query_terms(self, query: str) -> list[str]:
        normalised = norm(query)
        expanded = " ".join([normalised, *(extra for key, extra in SYNONYMS.items() if key in normalised)])
        return list(dict.fromkeys(t for t in tokens(expanded) if t not in STOPWORDS))

    def search(self, query: str, k: int = 3, k1: float = 1.5, b: float = 0.75) -> list[tuple[Clause, float]]:
        terms = self.query_terms(query)
        scored = []
        for clause, doc in zip(self.clauses, self._docs, strict=True):
            tf = Counter(doc)
            score = 0.0
            for term in terms:
                if term not in tf:
                    continue
                freq = tf[term]
                score += self._idf[term] * freq * (k1 + 1) / (
                    freq + k1 * (1 - b + b * len(doc) / self._avg_len))
            if score > 0:
                scored.append((clause, round(score, 3)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
