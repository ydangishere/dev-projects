"""Tests for Module 1 graph provenance, authorization boundaries and Neo4j adapter."""

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.engine import evaluate
from app.graph import (
    Neo4jGraph,
    build_snapshot,
    graph_evidence,
    merge_and_rerank,
    retrieve_module1,
)
from app.main import create_app
from app.providers import Source, extract_demo
from app.rag import policy_bundle, retrieve


ROOT = Path(__file__).resolve().parents[1]
CHECKER = {"Authorization": "Bearer demo-checker-token"}


def sample_graph(number=1):
    item = json.loads((ROOT / "samples/applications.json").read_text())[number - 1]
    application = {
        "id": item["id"],
        "tenant": item["tenant"],
        "revision": 1,
        **item["application"],
    }
    docs = item["documents"]
    extracted = {
        doc["id"]: extract_demo(Source(doc["text"].encode(), "text/plain", 1))
        for doc in docs
    }
    rules, md, _ = policy_bundle("pvcb", date(2026, 11, 5))
    findings = evaluate(application, docs, extracted, rules, date(2026, 11, 5), "demo")
    sections = retrieve(md, "required verification", set(rules["rules"].values()))
    return application, docs, findings, rules, sections


def test_local_graph_links_findings_to_documents_and_policy():
    application, docs, findings, rules, sections = sample_graph()
    result, ranked, warning = retrieve_module1(
        application, docs, findings, rules, sections
    )
    assert result["backend"] == "local"
    assert warning is None
    assert {row["finding_id"] for row in result["evidence"]} == {
        finding.id for finding in findings
    }
    missing = next(row for row in result["evidence"] if row["finding_code"] == "missing_document")
    assert missing["rule"] == "R1"
    assert missing["missing_required_kind"] == "bank_confirmation"
    assert missing["document_id"] is None
    expired = next(row for row in result["evidence"] if row["finding_code"] == "expired")
    assert expired["rule"] == "R2"
    assert expired["document_kind"] == "representative_id"
    assert "policy" in expired["path"]
    assert {section["rule"] for section in ranked} == {f"R{i}" for i in range(1, 8)}
    assert ranked[0]["graph_score"] >= ranked[-1]["graph_score"]


def test_clean_application_never_invents_graph_findings():
    application, docs, findings, rules, sections = sample_graph(3)
    assert findings == []
    result, ranked, _ = retrieve_module1(application, docs, findings, rules, sections)
    assert result["evidence"] == []
    assert len(ranked) == len(sections)
    assert all(section["graph_score"] == 0 for section in ranked)


def test_neo4j_adapter_reads_real_edge_result_with_pseudonymous_tokens():
    application, docs, findings, rules, _ = sample_graph()
    snapshot = build_snapshot(application, docs, findings, rules)
    seen = {"runs": []}

    class FakeResult(list):
        def consume(self):
            return None

    class Tx:
        def run(self, query, **params):
            seen["runs"].append((query, params))
            if "RETURN a.token AS source" in query:
                return FakeResult([
                    {
                        "source": link["source"],
                        "relation": link["relation"],
                        "target": link["target"],
                    }
                    for link in seen["links"]
                ])
            if "UNWIND $nodes" in query:
                seen["nodes"] = params["nodes"]
            if "UNWIND $links" in query:
                seen["links"] = params["links"]
            return FakeResult()

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute_write(self, operation):
            return operation(Tx())

    class Driver:
        def session(self, **kwargs):
            assert kwargs["database"] == "neo4j"
            return Session()

    backend = object.__new__(Neo4jGraph)
    backend.driver = Driver()
    backend.database = "neo4j"
    backend.secret = b"long-demo-hmac-secret-32-characters!"
    edges = backend.retrieve_edges(application["tenant"], application["id"], snapshot)
    assert len(edges) == len(snapshot["edges"])
    assert set((e["source"], e["relation"], e["target"]) for e in edges) == {
        (e["source"], e["relation"], e["target"]) for e in snapshot["edges"]
    }
    # Neo4j receives no unmasked application ID, tenant, document IDs, or PII.
    serialized = json.dumps(seen["nodes"] + seen["links"])
    assert application["id"] not in serialized
    assert application["tenant"] not in serialized
    for doc in docs:
        assert doc["id"] not in serialized
    assert "legal_name" not in serialized
    assert any("RETURN a.token" in query for query, _ in seen["runs"])


def test_unavailable_neo4j_uses_local_graph_without_changing_findings(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_BACKEND", raising=False)
    monkeypatch.delenv("TOKENS_JSON", raising=False)
    app = create_app(tmp_path, "demo")

    class Unavailable:
        def retrieve_edges(self, *_args):
            raise OSError("database down")

    app.state.graph_backend = Unavailable()
    response = TestClient(app).post(
        "/api/applications/APP-DEMO-001/checks",
        headers=CHECKER,
        json={"question": "kiểm tra hồ sơ"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["graph_retrieval"]["backend"] == "local"
    assert {f["code"] for f in body["findings"]} == {
        "missing_document", "expired", "unverified_version"
    }
    assert {"stage": "graph", "status": "neo4j_unavailable_local_fallback"} in body["events"]


def test_graph_evidence_is_tenant_authorized_through_existing_check_api(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_BACKEND", raising=False)
    monkeypatch.delenv("TOKENS_JSON", raising=False)
    client = TestClient(create_app(tmp_path, "demo"))
    response = client.post(
        "/api/applications/APP-DEMO-001/checks",
        headers=CHECKER,
        json={},
    )
    assert response.status_code == 201
    result = response.json()
    finding_id = result["findings"][0]["id"]
    evidence = client.get(
        f"/api/checks/{result['id']}/evidence/{finding_id}", headers=CHECKER
    ).json()
    assert evidence["graph"]["finding_id"] == finding_id
    assert evidence["graph"]["rule"] == evidence["policy"]["rule"]
    assert client.get(
        f"/api/checks/{result['id']}/evidence/{finding_id}"
    ).status_code == 401
    assert client.post(
        "/api/applications/APP-OTHER-001/checks", json={}, headers=CHECKER
    ).status_code == 404


def test_neo4j_graph_path_controls_evidence_not_document_content():
    application, docs, findings, rules, sections = sample_graph()
    snapshot = build_snapshot(application, docs, findings, rules)

    class FakeNeo4j:
        def retrieve_edges(self, tenant, application_id, value):
            assert tenant == "pvcb"
            assert application_id == application["id"]
            assert value == snapshot
            return list(value["edges"])

    result, ranked, warning = retrieve_module1(
        application, docs, findings, rules, sections, FakeNeo4j()
    )
    assert warning is None
    assert result["backend"] == "neo4j"
    assert len(result["evidence"]) == len(findings)
    assert all("legal_name" not in str(row) for row in result["evidence"])


def test_graph_rerank_never_eliminates_policy_sections():
    application, docs, findings, rules, sections = sample_graph(2)
    snapshot = build_snapshot(application, docs, findings, rules)
    evidence = graph_evidence(snapshot, docs, findings)
    merged = merge_and_rerank(sections, evidence, findings)
    assert len(merged) == len(sections)
    assert {section["rule"] for section in merged} == set(rules["rules"].values())
    assert merged[0]["rule"] == "R3"
