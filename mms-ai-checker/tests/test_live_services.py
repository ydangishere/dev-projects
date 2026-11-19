"""Integration tests against real services. Skipped unless the service is configured.

Local run (Docker):
  docker run -d --name mms-neo4j -p 127.0.0.1:7687:7687 -e NEO4J_AUTH=neo4j/<password> neo4j:5.26
  NEO4J_LIVE_URI=bolt://127.0.0.1:7687 NEO4J_LIVE_PASSWORD=<password> pytest tests/test_live_services.py
"""

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.graph import Neo4jGraph, build_snapshot, retrieve_module1
from app.main import create_app
from tests.test_graph import CHECKER, sample_graph

NEO4J = os.getenv("NEO4J_LIVE_URI")
HMAC = "live-test-hmac-secret-with-32-plus-characters"
neo4j_only = pytest.mark.skipif(not NEO4J, reason="set NEO4J_LIVE_URI and NEO4J_LIVE_PASSWORD")


@pytest.fixture
def neo4j_backend():
    backend = Neo4jGraph(NEO4J, "neo4j", os.environ["NEO4J_LIVE_PASSWORD"], HMAC)
    yield backend
    with backend.driver.session(database="neo4j") as session:
        session.run("MATCH (n:MMSGraphNode) DETACH DELETE n").consume()
    backend.close()


@neo4j_only
def test_live_neo4j_round_trip_matches_local_graph(neo4j_backend):
    application, docs, findings, rules, sections = sample_graph()
    snapshot = build_snapshot(application, docs, findings, rules)
    edges = neo4j_backend.retrieve_edges("pvcb", application["id"], snapshot)
    assert {(e["source"], e["relation"], e["target"]) for e in edges} == {
        (e["source"], e["relation"], e["target"]) for e in snapshot["edges"]
    }
    result, _, warning = retrieve_module1(
        application, docs, findings, rules, sections, neo4j_backend
    )
    local, _, _ = retrieve_module1(application, docs, findings, rules, sections)
    assert warning is None and result["backend"] == "neo4j"
    assert result["evidence"] == local["evidence"]


@neo4j_only
def test_live_neo4j_stores_only_pseudonymous_tokens(neo4j_backend):
    application, docs, findings, rules, _ = sample_graph()
    neo4j_backend.retrieve_edges(
        "pvcb", application["id"], build_snapshot(application, docs, findings, rules)
    )
    with neo4j_backend.driver.session(database="neo4j") as session:
        stored = [dict(r["n"]) for r in session.run("MATCH (n:MMSGraphNode) RETURN n")]
    text = json.dumps(stored, ensure_ascii=False)
    assert stored
    for secret in [application["id"], "pvcb", application.get("legal_name", "@@"), *[d["id"] for d in docs]]:
        assert secret not in text


@neo4j_only
def test_live_neo4j_scopes_are_isolated_and_rewritten(neo4j_backend):
    application, docs, findings, rules, _ = sample_graph()
    snapshot = build_snapshot(application, docs, findings, rules)
    neo4j_backend.retrieve_edges("pvcb", application["id"], snapshot)
    neo4j_backend.retrieve_edges("other-bank", application["id"], snapshot)
    neo4j_backend.retrieve_edges("pvcb", application["id"], snapshot)  # replace, not append
    with neo4j_backend.driver.session(database="neo4j") as session:
        scopes = session.run(
            "MATCH (n:MMSGraphNode) RETURN n.scope AS scope, count(*) AS nodes"
        ).data()
    assert len(scopes) == 2
    assert len({row["nodes"] for row in scopes}) == 1


@neo4j_only
def test_live_neo4j_through_check_api(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKENS_JSON", raising=False)
    monkeypatch.setenv("GRAPH_BACKEND", "neo4j")
    monkeypatch.setenv("NEO4J_URI", NEO4J)
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", os.environ["NEO4J_LIVE_PASSWORD"])
    monkeypatch.setenv("GRAPH_HMAC_KEY", HMAC)
    app = create_app(tmp_path, "demo")
    try:
        response = TestClient(app).post(
            "/api/applications/APP-DEMO-001/checks", headers=CHECKER, json={}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["graph_retrieval"]["backend"] == "neo4j"
        assert not [e for e in body["events"] if e["stage"] == "graph"]
    finally:
        app.state.graph_backend.close()


# ---------------------------------------------------------------- pgvector

PGVECTOR = os.getenv("PGVECTOR_LIVE_DSN")
pgvector_only = pytest.mark.skipif(not PGVECTOR, reason="set PGVECTOR_LIVE_DSN")


class CountingEmbedder:
    def __init__(self):
        from app.retrieval import HashingEmbedder

        self.inner, self.name, self.calls = HashingEmbedder(), "local-hashing-v1", []

    def embed(self, texts):
        self.calls.append(len(texts))
        return self.inner.embed(texts)


@pytest.fixture
def pg_store():
    from app.vectorstore import PgVectorStore

    store = PgVectorStore(PGVECTOR)
    with store._connect() as db:
        db.execute("DELETE FROM mms_policy_chunks")
    yield store
    with store._connect() as db:
        db.execute("DELETE FROM mms_policy_chunks")


@pgvector_only
def test_live_pgvector_matches_memory_index(pg_store):
    from app.retrieval import HybridRetriever
    from app.retrieval_eval import run_experiment

    memory = run_experiment(HybridRetriever(), "all")
    persisted = run_experiment(HybridRetriever(store=pg_store), "all")
    assert persisted["hybrid"] == memory["hybrid"]
    assert {q: v["hybrid"] for q, v in persisted["per_question"].items()} == {
        q: v["hybrid"] for q, v in memory["per_question"].items()
    }


@pgvector_only
def test_live_pgvector_persists_embeddings_across_instances(pg_store):
    from datetime import date

    from app.rag import policy_bundle
    from app.retrieval import HybridRetriever

    rules, md, _ = policy_bundle("pvcb", date(2026, 11, 5))
    first, second = CountingEmbedder(), CountingEmbedder()
    args = (md, rules, "pvcb", "2026-11-05", "giấy phép hết hạn", set())
    sections, trace = HybridRetriever(first, store=pg_store).search(*args)
    again, trace2 = HybridRetriever(second, store=pg_store).search(*args)
    assert trace["vector_store"] == "pgvector" and trace["status"] is None
    assert len(first.calls) == 2  # chunk index + query
    assert len(second.calls) == 1  # query only: chunk embeddings came from Postgres
    assert again == sections
    with pg_store._connect() as db:
        columns = [r[0] for r in db.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'mms_policy_chunks'"
        ).fetchall()]
    assert "text" not in columns and "question" not in columns


@pgvector_only
def test_pgvector_outage_falls_back_without_losing_rules(pg_store):
    from datetime import date

    from app.rag import policy_bundle
    from app.retrieval import HybridRetriever

    class Down:
        name = "pgvector"

        def has(self, *_):
            raise OSError("connection refused")

    rules, md, _ = policy_bundle("pvcb", date(2026, 11, 5))
    required = set(rules["rules"].values())
    sections, trace = HybridRetriever(store=Down()).search(
        md, rules, "pvcb", "2026-11-05", "x", required
    )
    assert trace["status"] == "vector_index_unavailable_local_fallback"
    assert trace["vector_store"] == "memory"
    assert required <= {s["rule"] for s in sections}
