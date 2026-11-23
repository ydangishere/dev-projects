"""Offline regression tests for DXA Agentic planning/replanning and session safety."""
from pathlib import Path
from tempfile import TemporaryDirectory

import diagnostic


def case_result(query):
    return {
        "context": "Trường hợp C02: bình xăng con chảy xăng [C02]",
        "case_ids": ["C02"], "case_idx": [0], "sources": [
            {"type": "case", "id": "C02", "video_title": "Demo", "time": "0:10", "link": "https://example.test"}
        ],
        "in_scope": True, "near": False,
    }


def answer(question, evidence):
    assert "đề quay" in question.lower(), question
    assert evidence["case_ids"] == ["C02"]
    return {"answer": "Kiểm tra có căn cứ [C02].", "sources": evidence["sources"], "refused": False, "warnings": []}


def planner(context):
    history = context["history"]
    user_msgs = [h["text"].lower() for h in history if h["role"] == "user"]
    if len(user_msgs) == 1:
        return {"action": "ask_user", "question": "Khi bấm đề, động cơ có quay không?"}
    if not context["evidence"]:
        return {"action": "search_rag", "query": "xe đề quay nhưng không nổ"}
    return {"action": "answer"}


def test_dialogue(db):
    first = diagnostic.run_turn(
        "Xe tôi không nổ máy", planner=planner, retriever=case_result, answerer=answer, db_path=db
    )
    assert first["status"] == "ask_user", first
    second = diagnostic.run_turn(
        "Đề quay nhưng không nổ", session_id=first["session_id"],
        planner=planner, retriever=case_result, answerer=answer, db_path=db
    )
    assert second["status"] == "answer" and "[C02]" in second["answer"], second
    assert second["turns"] == 2 and second["sources"], second
    assert second["actions"][0]["action"] == "search_rag", second
    try:
        diagnostic.run_turn("Đề quay", first["session_id"], planner=planner, retriever=case_result, answerer=answer, db_path=db)
        raise AssertionError("Finished session must not be reused")
    except ValueError:
        pass


def test_no_evidence(db):
    def no_evidence(_query):
        return {"context": "", "case_ids": [], "case_idx": [], "sources": [], "in_scope": False, "near": False}
    seq = iter([{"action": "search_rag", "query": "không có dữ liệu"}, {"action": "answer"}])
    result = diagnostic.run_turn(
        "Xe có triệu chứng không xác định", planner=lambda _: next(seq),
        retriever=no_evidence, answerer=answer, db_path=db
    )
    assert result["status"] == "handoff" and result["sources"] == [], result


def test_loop_bound(db):
    i = [0]
    def endless(_):
        i[0] += 1
        return {"action": "search_rag", "query": f"query-{i[0]}"}
    result = diagnostic.run_turn(
        "Xe khó nổ", planner=endless, retriever=case_result, answerer=answer, db_path=db
    )
    assert result["status"] == "handoff" and i[0] <= diagnostic.MAX_STEPS_PER_TURN


def test_invalid_sessions(db):
    for sid in ("bad", "a" * 32):
        try:
            diagnostic.run_turn("Xe không nổ", sid, planner=planner, retriever=case_result, answerer=answer, db_path=db)
            raise AssertionError(f"Invalid/missing session accepted: {sid}")
        except ValueError:
            pass


def test_parser():
    import dxa_tools
    assert dxa_tools.parse_plan('{"action":"search_rag","query":"honda wave"}')["action"] == "search_rag"
    assert dxa_tools.parse_plan('{"action":"rm -rf"}') == {"action": "handoff"}
    assert dxa_tools.parse_plan("not json") == {"action": "handoff"}


if __name__ == "__main__":
    with TemporaryDirectory() as folder:
        db = Path(folder) / "sessions.sqlite3"
        test_dialogue(db)
        test_no_evidence(db)
        test_loop_bound(db)
        test_invalid_sessions(db)
    test_parser()
    print("DXA Agentic: 5/5 tests passed")
