"""Vector index backends for policy retrieval.

VECTOR_STORE=memory (default) keeps chunk embeddings in the process. VECTOR_STORE=pgvector
persists them in PostgreSQL with the pgvector extension (PGVECTOR_DSN), so embeddings
survive restarts and are shared by several app instances, and paid embedding calls
(Gemini) are made once per policy version and chunk setting, not once per process.

What is stored: an index namespace (hash of policy text, embedder and chunk settings),
chunk ID, rule ID, tenant, policy version and the embedding. Policy text, applications,
documents and employee questions are not stored. Similarity search is exact cosine
distance limited to the chunk IDs that already passed server-side metadata filtering,
plus a tenant condition in SQL as a second guard.
"""

from __future__ import annotations

import os


def _ranked(scores: dict[str, float], k: int) -> list[tuple[str, float]]:
    return sorted(
        ((cid, s) for cid, s in scores.items() if s > 0), key=lambda x: (-x[1], x[0])
    )[:k]


class MemoryVectorStore:
    name = "memory"

    def __init__(self):
        self.vectors: dict[str, dict[str, list[float]]] = {}

    def has(self, namespace: str, count: int) -> bool:
        return len(self.vectors.get(namespace, {})) == count

    def upsert(self, namespace: str, chunks, vectors) -> None:
        self.vectors[namespace] = {c.id: v for c, v in zip(chunks, vectors)}

    def search(self, namespace, query, allowed_ids, tenant, k):
        stored = self.vectors[namespace]
        scores = {cid: sum(a * b for a, b in zip(query, stored[cid])) for cid in allowed_ids}
        return _ranked(scores, k)


class PgVectorStore:
    """PostgreSQL + pgvector. Requires `pip install -r requirements-vector.txt`."""

    name = "pgvector"

    def __init__(self, dsn: str, connect_timeout: int = 5):
        if not dsn:
            raise ValueError("VECTOR_STORE=pgvector requires PGVECTOR_DSN")
        import psycopg

        self.psycopg = psycopg
        self.dsn, self.timeout = dsn, connect_timeout
        with self._connect() as db:
            db.execute("CREATE EXTENSION IF NOT EXISTS vector")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS mms_policy_chunks (
                    namespace TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    rule TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    embedding vector NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (namespace, chunk_id)
                )
                """
            )

    def _connect(self):
        return self.psycopg.connect(self.dsn, connect_timeout=self.timeout, autocommit=True)

    @staticmethod
    def _literal(vector) -> str:
        return "[" + ",".join(f"{float(v):.8g}" for v in vector) + "]"

    def has(self, namespace: str, count: int) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT count(*) FROM mms_policy_chunks WHERE namespace = %s", (namespace,)
            ).fetchone()
        return row[0] == count

    def upsert(self, namespace: str, chunks, vectors) -> None:
        with self._connect() as db, db.transaction():
            db.execute("DELETE FROM mms_policy_chunks WHERE namespace = %s", (namespace,))
            with db.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO mms_policy_chunks "
                    "(namespace, chunk_id, rule, tenant, policy_version, embedding) "
                    "VALUES (%s, %s, %s, %s, %s, %s::vector)",
                    [
                        (namespace, c.id, c.rule, c.tenant, c.version, self._literal(v))
                        for c, v in zip(chunks, vectors)
                    ],
                )

    def search(self, namespace, query, allowed_ids, tenant, k):
        literal = self._literal(query)
        with self._connect() as db:
            rows = db.execute(
                "SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score "
                "FROM mms_policy_chunks "
                "WHERE namespace = %s AND tenant = %s AND chunk_id = ANY(%s) "
                "ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s",
                (literal, namespace, tenant, sorted(allowed_ids), literal, k),
            ).fetchall()
        return [(cid, float(score)) for cid, score in rows if score > 0]


def build_vector_store(mode: str | None = None):
    mode = (mode or os.getenv("VECTOR_STORE", "memory")).casefold()
    if mode == "memory":
        return MemoryVectorStore()
    if mode == "pgvector":
        return PgVectorStore(os.getenv("PGVECTOR_DSN", ""))
    raise ValueError("VECTOR_STORE must be memory or pgvector")
