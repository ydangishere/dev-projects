"""Kiểm tab "Bổ sung kiến thức" qua API thật (FastAPI TestClient):

  1. Chưa đăng nhập thợ thì mọi API ghi / xem câu chưa trả lời đều bị chặn (401), kể cả gọi thẳng API.
  2. Sai mã thì không vào được, đúng mã thì có token.
  3. Câu "lốp xe bị xì hơi" lúc đầu bị từ chối và nằm trong danh sách câu chưa trả lời được.
  4. Thợ lưu case T01 -> kho dựng lại -> DXA trả lời được bằng T01, câu đó biến khỏi danh sách.
  5. Thợ gỡ T01 -> DXA lại từ chối. Dữ liệu sai (thiếu triệu chứng) bị trả 422.

Chạy:  python test_expert.py   (cần đã chạy `python dxa.py build`)
Test tự dọn file knowledge_expert*.json và trả lại unanswered.jsonl như cũ khi chạy xong.
"""
import os
import sys

os.environ["DXA_THO_CODE"] = "246810"  # mã cố định cho test, đặt trước khi import api

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import dxa  # noqa: E402
import expert  # noqa: E402

Q = "lốp xe bị xì hơi"
fails = []


def check(cond, msg):
    print(("OK   " if cond else "LỖI ") + msg)
    if not cond:
        fails.append(msg)


backup = expert.UNANSWERED_FILE.read_bytes() if expert.UNANSWERED_FILE.exists() else None
had_expert = expert.EXPERT_FILE.exists()
if had_expert:
    sys.exit("Đã có data/knowledge_expert.json (kiến thức thợ thật): không chạy test để khỏi đụng dữ liệu đó.")

try:
    with TestClient(api.app) as cl:
        # 1. chặn khi chưa đăng nhập
        check(cl.get("/unanswered").status_code == 401, "xem câu chưa trả lời khi chưa đăng nhập -> 401")
        check(cl.post("/tho/cases", json={"symptom": "a", "cause": "b", "fix": "c"}).status_code == 401,
              "lưu case khi chưa đăng nhập -> 401")
        check(cl.get("/tho/cases", headers={"Authorization": "Bearer gia-mao"}).status_code == 401, "token giả -> 401")

        # 2. đăng nhập
        check(cl.post("/tho/login", json={"code": "000000"}).status_code == 401, "sai mã -> 401")
        r = cl.post("/tho/login", json={"code": "246810"})
        check(r.status_code == 200 and r.json().get("token"), "đúng mã -> có token")
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        check(cl.get("/tho/me", headers=H).status_code == 200, "token thợ dùng được")

        # 3. lúc đầu chưa trả lời được
        a = cl.post("/ask", json={"question": Q}).json()
        check(a["refused"], "trước khi bổ sung: DXA từ chối")
        uq = cl.get("/unanswered", headers=H).json()
        check(any(expert.rag.bare(u["question"]) == expert.rag.bare(Q) for u in uq), "câu hỏi nằm trong danh sách chưa trả lời")

        # 4. thợ lưu kiến thức
        bad = cl.post("/tho/cases", headers=H, json={"symptom": "", "cause": "b", "fix": "c"})
        check(bad.status_code == 422, "thiếu triệu chứng -> 422")
        case = {"symptom": "Lốp xe bị xì hơi, xẹp dần sau một đêm", "cause": "Ruột xe bị đinh đâm hoặc van ruột xe hở",
                "fix": "Bơm hơi, nhúng ruột vào chậu nước tìm chỗ sủi bọt, vá ruột hoặc thay van", "system": "khác",
                "parts": ["ruột xe", "van ruột xe"], "specs": [{"name": "áp suất lốp sau", "value": "33", "unit": "psi"}],
                "author": "test", "from_question": Q}
        s = cl.post("/tho/cases", headers=H, json=case)
        check(s.status_code == 200 and s.json()["case"]["id"] == "T01", "lưu case -> T01")
        a = cl.post("/ask", json={"question": Q}).json()
        top = next((x for x in a["sources"] if x["type"] == "case"), {})
        check(not a["refused"] and top.get("id") == "T01", f"sau khi bổ sung: DXA trả lời bằng T01 (ra {top.get('id')}, by={a['answered_by']})")
        check(top.get("source") == "tho" and top.get("link") == "", "nguồn T01 ghi là thợ nhập, không có link video")
        uq = cl.get("/unanswered", headers=H).json()
        check(not any(expert.rag.bare(u["question"]) == expert.rag.bare(Q) for u in uq), "câu đã bổ sung biến khỏi danh sách")
        a = cl.post("/ask", json={"question": "Bình xăng con chảy xăng khi dựng xe"}).json()
        check(next(x["id"] for x in a["sources"] if x["type"] == "case") == "C02", "câu cũ vẫn trả lời bằng case video C02")

        # 5. gỡ case
        check(cl.delete("/tho/cases/T01", headers=H).status_code == 200, "gỡ T01")
        check(cl.post("/ask", json={"question": Q}).json()["refused"], "sau khi gỡ: DXA lại từ chối")
        check(cl.post("/tho/logout", headers=H).status_code == 200 and cl.get("/tho/me", headers=H).status_code == 401,
              "đăng xuất -> token hết dùng")
finally:
    for f in (expert.EXPERT_FILE, expert.HISTORY_FILE):
        f.unlink(missing_ok=True)
    if backup is None:
        expert.UNANSWERED_FILE.unlink(missing_ok=True)
    else:
        expert.UNANSWERED_FILE.write_bytes(backup)
    dxa.build()  # trả kho về như trước khi test

print("\nKẾT QUẢ:", "ĐẠT" if not fails else f"LỖI {len(fails)}")
sys.exit(1 if fails else 0)
