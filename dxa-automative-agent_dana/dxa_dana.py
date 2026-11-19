"""Cầu nối Python -> agent Dana (dxa_agent.na).

1. configure(): cho reason() của Dana dùng Gemini qua cổng tương thích OpenAI
   (Dana gọi đây là model "local"), bằng key GEMINI_API_KEY trong file .env.
2. ask(question): gọi hàm ask() trong dxa_agent.na, trả về cùng dạng với rag.answer()
   để giao diện web và API dùng y như cũ.

Phải gọi configure() TRƯỚC khi import dana.
"""
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_agent = None


def configure():
    import gemini_client as G  # đọc .env, đặt GEMINI_API_KEY nếu có

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        os.environ.setdefault("LOCAL_API_KEY", key)
        os.environ.setdefault("LOCAL_BASE_URL", GEMINI_OPENAI_URL)
        os.environ.setdefault("LOCAL_MODEL_NAME", G.LLM_MODEL)

    # Cấu hình Dana: lấy file cấu hình mặc định của gói dana, thêm model "local" (Gemini ở trên) lên đầu
    cfg = {}
    try:
        import importlib.util

        spec = importlib.util.find_spec("dana")
        if spec and spec.origin:
            default = Path(spec.origin).parent / "dana_config.json"
            if default.exists():
                cfg = json.loads(default.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    llm = cfg.setdefault("llm", {})
    llm["preferred_models"] = ["local"] + [m for m in llm.get("preferred_models", []) if m != "local"]
    llm.setdefault("provider_configs", {})["local"] = {
        "api_type": "openai",
        "api_key": "env:LOCAL_API_KEY",
        "base_url": "env:LOCAL_BASE_URL",
        "model_name": "env:LOCAL_MODEL_NAME",
    }
    path = BASE / "index" / "dana_config.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    os.environ.setdefault("DANA_CONFIG", str(path))


def _load_agent():
    global _agent
    if _agent is None:
        configure()
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from dana.integrations.python.to_dana import dana

        dana.enable_module_imports([str(BASE)])
        import dxa_agent  # file dxa_agent.na

        _agent = dxa_agent
    return _agent


def _plain(v):
    """Đổi giá trị Dana trả về sang kiểu Python thường để FastAPI trả JSON được.

    Hàm Dana có thể trả về "promise" (giá trị tính trễ): chờ lấy giá trị thật trước.
    """
    for _ in range(5):
        if hasattr(v, "_wait_for_delivery"):
            v = v._wait_for_delivery()
        else:
            break
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def ask(question: str) -> dict:
    """Hỏi agent Dana. Dana lỗi thì vẫn trả lời bằng bản Python (rag.py) và ghi cảnh báo."""
    try:
        r = _plain(_load_agent().ask(question))
        r.setdefault("warnings", [])
        r["near"] = bool(r.get("near"))
        return r
    except Exception as e:
        import rag

        r = rag.answer(question)
        r = {k: r.get(k) for k in ("question", "query_used", "answer", "refused", "near", "answered_by", "mode", "warnings", "sources")}
        r["near"] = bool(r["near"])
        r["answered_by"] = f"python ({r['answered_by']})"
        r["warnings"] = r["warnings"] + [f"Agent Dana lỗi, dùng bản Python: {e.__class__.__name__}: {e}"]
        return r


if __name__ == "__main__":
    res = ask(" ".join(sys.argv[1:]) or "Bình xăng con chảy xăng khi dựng xe")
    print(res["answer"])
    print(f"[chế độ: {res['mode']}, trả lời bởi: {res['answered_by']}]")
    for w in res["warnings"]:
        print("!", w)
