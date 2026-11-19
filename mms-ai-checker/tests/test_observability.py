import sys
import types

from app import observability
from app.retrieval import HybridRetriever


def test_tracing_is_a_no_op_without_key(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    def func():
        return 1

    assert observability.traced("x")(func) is func


def test_tracing_wraps_with_redacted_inputs_when_enabled(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    captured = {}

    def fake_traceable(**options):
        captured.update(options)
        return lambda func: ("wrapped", func)

    monkeypatch.setitem(sys.modules, "langsmith", types.SimpleNamespace(traceable=fake_traceable))
    wrapped = observability.traced("policy_retrieval", run_type="retriever")(lambda: None)
    assert wrapped[0] == "wrapped" and captured["run_type"] == "retriever"

    retriever = HybridRetriever()
    slim = captured["process_inputs"](
        {
            "self": retriever,
            "md": "FULL POLICY TEXT",
            "rules": {"secret": True},
            "tenant": "pvcb",
            "review_date": "2026-11-05",
            "query": "hết hạn",
            "required_rule_ids": {"R2", "R1"},
        }
    )
    assert "md" not in slim and "rules" not in slim
    assert slim["required_rule_ids"] == ["R1", "R2"]
    assert slim["embedder"] == "local-hashing-v1"

    out = captured["process_outputs"](
        ([{"rule": "R2", "score": 1.0, "text": "policy text", "chunk_ids": ["c"]}], {"status": None})
    )
    assert out["sections"] == [{"rule": "R2", "score": 1.0, "chunk_ids": ["c"]}]
