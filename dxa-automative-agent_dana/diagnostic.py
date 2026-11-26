"""DXA diagnostic agent loop: bounded planning, retrieval, and multi-turn memory.

Planner is provided by Dana (dxa_agent.na). No diagnosis is claimed without
evidence from the existing RAG store. This local prototype is not an ECU reader.
"""
import json
import re
import secrets
import sqlite3
from observability import observe, traced, update, result_metadata
import time
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).parent / "index" / "diagnostic_sessions.sqlite3"
MAX_TURNS = 12
MAX_STEPS_PER_TURN = 4
MAX_TOTAL_SEARCHES = 12
SESSION_TTL = 24 * 60 * 60
SESSION_RE = re.compile(r"^[a-f0-9]{32}$")
UNSUPPORTED = "Chưa đủ bằng chứng từ kho sửa xe để kết luận. Hãy nhờ thợ kiểm tra trực tiếp."


def _connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path), timeout=10)
    c.execute(
        "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, updated REAL NOT NULL, state TEXT NOT NULL)"
    )
    c.execute("DELETE FROM sessions WHERE updated < ?", (time.time() - SESSION_TTL,))
    c.commit()
    return c


def _load(c, session_id):
    if not session_id:
        return secrets.token_hex(16), {
            "history": [], "evidence": [], "queries": [], "turns": 0, "status": "active"
        }
    if not SESSION_RE.fullmatch(session_id):
        raise ValueError("Mã phiên chẩn đoán không hợp lệ")
    row = c.execute("SELECT state FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        raise ValueError("Phiên chẩn đoán đã hết hạn hoặc không tồn tại; hãy bắt đầu phiên mới")
    return session_id, json.loads(row[0])


def _save(c, session_id, state):
    c.execute(
        "INSERT INTO sessions(id,updated,state) VALUES(?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET updated=excluded.updated,state=excluded.state",
        (session_id, time.time(), json.dumps(state, ensure_ascii=False)),
    )
    c.commit()


def delete_session(session_id, db_path=DB_PATH):
    if not SESSION_RE.fullmatch(session_id):
        raise ValueError("Mã phiên chẩn đoán không hợp lệ")
    with closing(_connect(db_path)) as c, c:
        c.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        c.commit()


def _response(session_id, status, message, state, actions, sources=None, warnings=None):
    return {
        "session_id": session_id, "status": status, "answer": message,
        "sources": sources or [], "actions": actions,
        "turns": state["turns"], "warnings": warnings or [],
    }


def _context(state, actions):
    # Context is bounded; model sees recent dialogue, prior tool actions and cited cases.
    return {
        "history": state["history"][-16:],
        "evidence": [{
            "query": e["query"], "in_scope": e["in_scope"], "near": e["near"],
            "case_ids": e["case_ids"], "context": e["context"][:3500],
        } for e in state["evidence"][-2:]],
        "searched_queries": state["queries"][-12:],
        "actions_this_turn": actions,
        "remaining_turns": MAX_TURNS - state["turns"],
    }


@traced("dana.diagnose", "agent", result_metadata)
def run_turn(message, session_id=None, *, planner=None, retriever=None, answerer=None, db_path=DB_PATH):
    """Run at most four planner decisions and persist state between HTTP calls.

    Injectable dependencies enable deterministic offline tests. Only allowed
    actions are executed; the LLM cannot issue shell commands or write files.
    """
    message = message.strip()
    if not 2 <= len(message) <= 500:
        raise ValueError("Triệu chứng phải dài từ 2 đến 500 ký tự")
    if planner is None or answerer is None:
        import dxa_dana
        planner = planner or dxa_dana.plan_diagnostic
        answerer = answerer or dxa_dana.answer_diagnostic
    if retriever is None:
        import dxa_tools
        retriever = dxa_tools.retrieve

    with closing(_connect(db_path)) as c, c:
        sid, state = _load(c, session_id)
        if state["status"] != "active":
            raise ValueError("Phiên này đã kết thúc; hãy bắt đầu phiên chẩn đoán mới")
        state["turns"] += 1
        state["history"].append({"role": "user", "text": message})
        actions = []

        def finish(status, text, sources=None, warnings=None):
            state["history"].append({"role": "assistant", "text": text})
            state["status"] = "active" if status == "ask_user" else "done"
            state["history"] = state["history"][-24:]
            _save(c, sid, state)
            return _response(sid, status, text, state, actions, sources, warnings)

        if state["turns"] > MAX_TURNS:
            return finish("handoff", "Đã hết số lượt chẩn đoán an toàn. " + UNSUPPORTED)

        for _ in range(MAX_STEPS_PER_TURN):
            stage = "diagnostic.replan" if actions or state["turns"] > 1 else "diagnostic.plan"
            with observe(stage, "chain") as span:
                decision = planner(_context(state, actions))
                action_name = decision.get("action") if isinstance(decision, dict) else None
                allowed = {"search_rag", "ask_user", "answer", "handoff"}
                update(span, metadata={"action": action_name if action_name in allowed else "invalid"})
            if not isinstance(decision, dict):
                return finish("handoff", "AI không trả về kế hoạch hợp lệ. " + UNSUPPORTED)
            action = decision.get("action")
            if action == "search_rag":
                query = str(decision.get("query") or "").strip()[:200]
                if not query:
                    return finish("handoff", "Không có truy vấn tìm kiếm hợp lệ. " + UNSUPPORTED)
                if query in state["queries"]:
                    actions.append({"action": "duplicate_search", "query": query})
                    continue
                if len(state["queries"]) >= MAX_TOTAL_SEARCHES:
                    return finish("handoff", "Đã tới giới hạn tìm kiếm. " + UNSUPPORTED)
                with observe("diagnostic.search_rag", "tool"):
                    data = retriever(query)
                evidence = {
                    "query": query, "context": str(data.get("context") or "")[:9000],
                    "case_ids": list(data.get("case_ids") or [])[:10],
                    "case_idx": list(data.get("case_idx") or [])[:10],
                    "sources": list(data.get("sources") or [])[:12],
                    "in_scope": bool(data.get("in_scope")),
                    "near": bool(data.get("near")),
                }
                state["queries"].append(query)
                state["evidence"].append(evidence)
                state["evidence"] = state["evidence"][-4:]
                actions.append({"action": "search_rag", "query": query, "case_ids": evidence["case_ids"]})
                continue

            if action == "ask_user":
                question = str(decision.get("question") or "").strip()[:300]
                old_questions = {
                    h["text"] for h in state["history"] if h["role"] == "assistant"
                }
                if not question or question in old_questions:
                    return finish("handoff", "AI chưa tìm được câu hỏi bổ sung phù hợp. " + UNSUPPORTED)
                actions.append({"action": "ask_user"})
                return finish("ask_user", question)

            if action == "answer":
                relevant = next(
                    (e for e in reversed(state["evidence"]) if e["case_ids"] and (e["in_scope"] or e["near"])),
                    None,
                )
                if relevant is None:
                    actions.append({"action": "no_verified_evidence"})
                    return finish("handoff", UNSUPPORTED)
                question = " | ".join(
                    h["text"] for h in state["history"] if h["role"] == "user"
                )[-800:]
                result = answerer(question, relevant)
                actions.append({"action": "answer", "case_ids": relevant["case_ids"]})
                if result.get("refused") or not result.get("sources"):
                    return finish("handoff", UNSUPPORTED, warnings=result.get("warnings"))
                return finish("answer", str(result["answer"]), result["sources"], result.get("warnings"))

            if action == "handoff":
                actions.append({"action": "handoff"})
                return finish("handoff", UNSUPPORTED)

            return finish("handoff", "AI chọn hành động không được phép. " + UNSUPPORTED)

        # Avoid unbounded planner/tool calls even when model repeats searches.
        return finish("handoff", "Đã hết số bước lập kế hoạch của lượt này. " + UNSUPPORTED)
