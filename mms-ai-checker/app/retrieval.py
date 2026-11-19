"""Hybrid policy retrieval for AI Check (Module 1 RAG).

Pipeline per question:
query -> decomposition -> rewriting -> metadata filtering ->
hybrid search (vector + keyword, merged with Reciprocal Rank Fusion, deduplicated)
-> reranking -> rule-level policy sections.

Safety properties kept from the lexical retriever:
- Every executed rule section is always returned; a query can reorder but never drop it.
- Metadata filtering (tenant, effective date, policy version) runs before search and is
  derived from server-side policy data, never from the question text.
- The question is only used to rank approved policy text. It is not sent to a model
  unless EMBED_MODE=gemini is explicitly configured.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .observability import traced

DEFAULT_QUERY = (
    "required expiry matching verification uncertainty security human review"
)

STOPWORDS = {
    # English
    "a", "an", "and", "are", "be", "by", "can", "do", "does", "for", "how", "i", "if",
    "in", "is", "it", "of", "on", "or", "the", "this", "to", "what", "when", "which",
    "why", "with", "should", "must", "any", "has", "have",
    # Vietnamese (accent-folded forms are added automatically by tokenize)
    "có", "của", "cho", "này", "là", "và", "thì", "gì", "nào", "không", "được", "để",
    "các", "những", "một", "khi", "nếu", "với", "trong", "ra", "sao", "như", "thế",
    "hồ", "sơ", "cần", "phải", "bị", "đã", "còn",
}

# Domain rewriting: expand employee wording (VI/EN, with or without accents)
# into policy vocabulary. Original words are always kept.
REWRITE_TERMS = {
    "thiếu": "missing required documents absent",
    "bổ sung": "missing required documents",
    "giấy tờ": "documents required",
    "missing": "required documents absent",
    "hết hạn": "expiry expired expires_on date",
    "quá hạn": "expiry expired expires_on date",
    "ngày hết": "expiry expires_on date",
    "expire": "expiry expired expires_on date",
    "expiry": "expired expires_on date",
    "cccd": "representative_id expiry",
    "căn cước": "representative_id expiry",
    "khớp": "matching compare legal_name registration_number",
    "đối chiếu": "matching compare legal_name registration_number",
    "sai tên": "matching legal_name differences",
    "tên công ty": "matching legal_name business_license",
    "mã số": "matching registration_number",
    "mismatch": "matching compare differences legal_name",
    "match": "matching compare legal_name registration_number",
    "xác minh": "verification verified verified_version",
    "phiên bản": "verification version verified_version",
    "version": "verification verified_version",
    "verified": "verification verified_version",
    "chắc chắn": "uncertainty confidence manual verification",
    "độ tin cậy": "uncertainty confidence threshold",
    "confidence": "uncertainty threshold manual verification",
    "unclear": "uncertainty unknown manual verification",
    "chỉ dẫn": "security instructions untrusted",
    "lừa": "security instructions untrusted attempts",
    "prompt": "security instructions untrusted",
    "injection": "security instructions untrusted",
    "bỏ qua": "security instructions untrusted policy",
    "ignore": "security instructions untrusted policy",
    "duyệt": "human review approve decision employee",
    "phê duyệt": "human review approve decision employee",
    "approve": "human review decision employee",
    "quyết định": "human review decision employee",
    "chuyển tiền": "human review move money",
    "tài khoản ngân hàng": "bank_confirmation matching legal_name",
    "ngân hàng": "bank_confirmation",
    "giấy phép": "business_license",
    "đăng ký kinh doanh": "business_license registration_number",
}

_SPLIT = re.compile(r"[?;\n]+|\s+(?:và|and|đồng thời|also)\s+", re.IGNORECASE)


def _strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


_FOLDED_STOPWORDS = STOPWORDS | {_strip_accents(w) for w in STOPWORDS}


def tokenize(text: str) -> list[str]:
    """Word tokens plus accent-folded variants, so 'het han' matches 'hết hạn'."""
    tokens = []
    for word in re.findall(r"\w+", _norm(text)):
        if word in _FOLDED_STOPWORDS:
            continue
        tokens.append(word)
        folded = _strip_accents(word)
        if folded != word:
            tokens.append(folded)
    return tokens


def content_terms(text: str) -> set[str]:
    return {_strip_accents(t) for t in tokenize(text)}


@dataclass(frozen=True)
class Chunk:
    id: str
    rule: str
    title: str
    text: str
    section_text: str
    policy_id: str
    version: str
    tenant: str
    effective_from: str
    effective_to: str
    position: int


def chunk_policy(md: str, rules: dict, max_words: int = 60, overlap: int = 15) -> list[Chunk]:
    """Split policy Markdown into section-aware chunks with source metadata.

    Chunk size and overlap are configurable experiment settings, not tuned optima.
    """
    if overlap >= max_words:
        raise ValueError("overlap must be smaller than max_words")
    chunks = []
    for section in re.split(r"(?m)^## ", md)[1:]:
        title, _, body = section.partition("\n")
        rule = title.split()[0]
        words = body.split()
        step = max_words - overlap
        windows = [words[i : i + max_words] for i in range(0, max(len(words) - overlap, 1), step)]
        for index, window in enumerate(windows or [[]]):
            chunks.append(
                Chunk(
                    id=f"{rules['policy_id']}:{rules['version']}:{rule}:{index}",
                    rule=rule,
                    title=title.strip(),
                    text=f"{title.strip()}\n{' '.join(window)}".strip(),
                    section_text=section.strip(),
                    policy_id=rules["policy_id"],
                    version=str(rules["version"]),
                    tenant=rules["tenant"],
                    effective_from=str(rules["effective_from"]),
                    effective_to=str(rules["effective_to"]),
                    position=index,
                )
            )
    return chunks


def filter_chunks(chunks, tenant: str, review_date: str, version: str | None = None):
    """Metadata filter from server-authorized values; the question cannot widen it."""
    return [
        c
        for c in chunks
        if c.tenant == tenant
        and c.effective_from <= review_date <= c.effective_to
        and (version is None or c.version == version)
    ]


def decompose(query: str, limit: int = 4) -> list[str]:
    """Split multi-part questions; simple questions pass through unchanged."""
    parts = [p.strip(" .,:") for p in _SPLIT.split(query) if p and p.strip(" .,:")]
    parts = [p for p in parts if len(tokenize(p)) >= 1]
    if len(parts) <= 1:
        return [query.strip()]
    return parts[:limit]


def rewrite(query: str) -> str:
    """Append domain vocabulary for recognised phrases; never removes user words."""
    folded = _strip_accents(_norm(query))
    additions = []
    for phrase, expansion in REWRITE_TERMS.items():
        key = _strip_accents(_norm(phrase))
        if re.search(rf"(?<!\w){re.escape(key)}", folded) and expansion not in additions:
            additions.append(expansion)
    return " ".join([query.strip(), *additions]).strip()


class HashingEmbedder:
    """Deterministic local embedding: hashed words + character trigrams.

    Needs no network or model download. It captures spelling overlap, not deep
    meaning; use EMBED_MODE=gemini for a semantic embedding model.
    """

    name = "local-hashing-v1"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _features(self, text: str):
        for token in tokenize(text):
            yield "w:" + token
            padded = f"#{_strip_accents(token)}#"
            for i in range(len(padded) - 2):
                yield "c:" + padded[i : i + 3]

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for feature, count in Counter(self._features(text)).items():
                digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] & 1 else -1.0
                vec[index] += sign * (1.0 + math.log(count))
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class GeminiEmbedder:
    """Optional semantic embeddings through the Gemini API (EMBED_MODE=gemini)."""

    def __init__(self, client=None, model: str | None = None):
        if client is None:
            from google import genai

            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise ValueError("EMBED_MODE=gemini requires GEMINI_API_KEY")
            client = genai.Client(api_key=key)
        self.client = client
        self.model = model or os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
        self.name = f"gemini:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.models.embed_content(model=self.model, contents=texts)
        vectors = []
        for item in response.embeddings:
            values = list(item.values)
            norm = math.sqrt(sum(v * v for v in values)) or 1.0
            vectors.append([v / norm for v in values])
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding count mismatch")
        return vectors


class FastEmbedEmbedder:
    """Offline semantic embeddings with a multilingual ONNX model (EMBED_MODE=fastembed).

    Install with `pip install -r requirements-semantic.txt`. The model is downloaded once
    into FASTEMBED_CACHE_PATH (default: <DATA_DIR>/models) and then runs on CPU with no
    network calls. Text never leaves the server.
    """

    def __init__(self, model: str | None = None, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        self.model = model or os.getenv(
            "LOCAL_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        cache_dir = cache_dir or os.getenv("FASTEMBED_CACHE_PATH") or str(
            Path(os.getenv("DATA_DIR", "runtime")) / "models"
        )
        self._model = TextEmbedding(model_name=self.model, cache_dir=cache_dir)
        self.name = f"fastembed:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for values in self._model.embed(list(texts)):
            values = [float(v) for v in values]
            norm = math.sqrt(sum(v * v for v in values)) or 1.0
            vectors.append([v / norm for v in values])
        return vectors


class BM25:
    def __init__(self, docs: dict[str, list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.lengths = {key: len(tokens) for key, tokens in docs.items()}
        self.avg = sum(self.lengths.values()) / max(len(docs), 1)
        df = Counter(t for tokens in docs.values() for t in set(tokens))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = {key: Counter(tokens) for key, tokens in docs.items()}

    def search(self, query_tokens: list[str], allowed: set[str]):
        scores = {}
        for key in allowed:
            tf, length = self.tf[key], self.lengths[key]
            score = 0.0
            for term in set(query_tokens):
                if term not in tf:
                    continue
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * length / (self.avg or 1))
                score += self.idf.get(term, 0.0) * freq * (self.k1 + 1) / denom
            if score > 0:
                scores[key] = score
        return sorted(scores, key=lambda k: (-scores[k], k)), scores


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion; merging by id also removes duplicates."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    return fused


@dataclass
class RetrievalSettings:
    max_words: int = 60
    overlap: int = 15
    candidate_k: int = 8
    rrf_k: int = 60
    coverage_weight: float = 0.02


class HybridRetriever:
    def __init__(self, embedder=None, settings: RetrievalSettings | None = None):
        self.embedder = embedder or HashingEmbedder()
        self.fallback = HashingEmbedder()
        self.settings = settings or RetrievalSettings()
        self._cache: dict[tuple, tuple] = {}

    def _index(self, md: str, rules: dict, embedder):
        key = (hashlib.sha256(md.encode()).hexdigest(), embedder.name, self.settings.max_words, self.settings.overlap)
        if key not in self._cache:
            chunks = chunk_policy(md, rules, self.settings.max_words, self.settings.overlap)
            vectors = dict(zip([c.id for c in chunks], embedder.embed([c.text for c in chunks])))
            bm25 = BM25({c.id: tokenize(c.text) for c in chunks})
            self._cache[key] = (chunks, vectors, bm25)
        return self._cache[key]

    @traced("policy_retrieval", run_type="retriever")
    def search(self, md, rules, tenant, review_date, query, required_rule_ids):
        """Return (rule-level sections, retrieval trace)."""
        query = (query or "").strip() or DEFAULT_QUERY
        status = None
        embedder = self.embedder
        try:
            chunks, vectors, bm25 = self._index(md, rules, embedder)
        except Exception:
            embedder, status = self.fallback, "embedding_unavailable_local_fallback"
            chunks, vectors, bm25 = self._index(md, rules, embedder)

        allowed = filter_chunks(chunks, tenant, review_date, str(rules["version"]))
        allowed_ids = {c.id for c in allowed}
        by_id = {c.id: c for c in chunks}
        subqueries = decompose(query)
        rewritten = [rewrite(q) for q in subqueries]
        try:
            query_vectors = embedder.embed(rewritten)
        except Exception:
            embedder, status = self.fallback, "embedding_unavailable_local_fallback"
            chunks, vectors, bm25 = self._index(md, rules, embedder)
            query_vectors = embedder.embed(rewritten)

        rule_scores: dict[str, float] = {}
        rule_chunks: dict[str, list[str]] = {}
        candidates = []
        k = self.settings.candidate_k
        for sub, text, qvec in zip(subqueries, rewritten, query_vectors):
            vector_scores = {
                cid: sum(a * b for a, b in zip(qvec, vectors[cid])) for cid in allowed_ids
            }
            vector_rank = sorted(
                (cid for cid, s in vector_scores.items() if s > 0),
                key=lambda cid: (-vector_scores[cid], cid),
            )[:k]
            keyword_rank, _ = bm25.search(tokenize(text), allowed_ids)
            keyword_rank = keyword_rank[:k]
            fused = rrf([vector_rank, keyword_rank], self.settings.rrf_k)
            terms = content_terms(text)
            for cid, fused_score in fused.items():
                chunk_terms = content_terms(by_id[cid].text)
                coverage = len(terms & chunk_terms) / max(len(terms), 1)
                score = fused_score + self.settings.coverage_weight * coverage
                rule = by_id[cid].rule
                if score > rule_scores.get(rule, 0.0):
                    rule_scores[rule] = score
                rule_chunks.setdefault(rule, [])
                if cid not in rule_chunks[rule]:
                    rule_chunks[rule].append(cid)
                candidates.append(
                    {
                        "subquery": sub,
                        "chunk_id": cid,
                        "rule": rule,
                        "vector_rank": vector_rank.index(cid) + 1 if cid in vector_rank else None,
                        "keyword_rank": keyword_rank.index(cid) + 1 if cid in keyword_rank else None,
                        "rerank_score": round(score, 6),
                    }
                )

        sections_by_rule = {c.rule: c.section_text for c in allowed}
        sections = []
        for rule, text in sections_by_rule.items():
            if rule in rule_scores or rule in required_rule_ids:
                sections.append(
                    {
                        "rule": rule,
                        "text": text,
                        "score": round(rule_scores.get(rule, 0.0), 6),
                        "chunk_ids": rule_chunks.get(rule, []),
                    }
                )
        sections.sort(key=lambda s: (-s["score"], s["rule"]))
        candidates.sort(key=lambda c: (-c["rerank_score"], c["chunk_id"]))
        trace = {
            "method": "hybrid_vector_keyword_rrf_rerank",
            "embedder": embedder.name,
            "status": status,
            "subqueries": subqueries,
            "rewritten_queries": rewritten,
            "filters": {
                "tenant": tenant,
                "review_date": review_date,
                "policy_version": str(rules["version"]),
            },
            "chunks_indexed": len(chunks),
            "chunks_after_filter": len(allowed),
            "candidates": candidates[: 3 * k],
        }
        return sections, trace


EMBED_MODES = ("local", "fastembed", "gemini")


def build_embedder(mode: str | None = None):
    mode = (mode or os.getenv("EMBED_MODE", "local")).casefold()
    if mode == "gemini":
        return GeminiEmbedder()
    if mode == "fastembed":
        return FastEmbedEmbedder()
    if mode != "local":
        raise ValueError("EMBED_MODE must be local, fastembed or gemini")
    return HashingEmbedder()


def build_retriever(settings: RetrievalSettings | None = None):
    return HybridRetriever(build_embedder(), settings)
