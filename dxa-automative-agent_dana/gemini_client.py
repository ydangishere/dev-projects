"""Gọi Gemini: embedding + LLM. Có cache embedding trên đĩa để build lại không tốn tiền.

Cần:  pip install google-genai
      đặt biến môi trường GEMINI_API_KEY

Đổi model bằng biến môi trường (không cần sửa code):
  DXA_EMBED_MODEL   mặc định gemini-embedding-001
  DXA_EMBED_DIM     mặc định 768
  DXA_LLM_MODEL     mặc định gemini-3.6-flash
"""
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

def _load_dotenv(path=Path(__file__).parent / ".env"):
    """Đọc file .env cạnh code (KEY=VALUE mỗi dòng), để không phải đặt biến môi trường bằng tay."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

EMBED_MODEL = os.getenv("DXA_EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.getenv("DXA_EMBED_DIM", "768"))
LLM_MODEL = os.getenv("DXA_LLM_MODEL", "gemini-3.6-flash")
BATCH = 50

CACHE_FILE = Path(__file__).parent / "index" / "gemini_embed_cache.npz"

_client = None


def available():
    """Có key thì mới gọi Gemini; không có thì hệ thống chạy bản offline cũ."""
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def client():
    global _client
    if _client is None:
        from google import genai  # import muộn: không có thư viện vẫn chạy được bản offline
        _client = genai.Client()
    return _client


def _retry(fn, tries=5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # 429 / 503: chờ rồi thử lại
            msg = str(e)
            if i == tries - 1 or not any(code in msg for code in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
                raise
            time.sleep(2 ** i)


# ---------------------------------------------------------------- embedding
class _Cache:
    def __init__(self, path=CACHE_FILE):
        self.path = path
        self.data = {}
        if path.exists():
            z = np.load(path)
            self.data = {k: z[k] for k in z.files}
        self.dirty = False

    @staticmethod
    def key(text, task):
        return hashlib.sha1(f"{EMBED_MODEL}|{EMBED_DIM}|{task}|{text}".encode("utf-8")).hexdigest()

    def save(self):
        if self.dirty:
            self.path.parent.mkdir(exist_ok=True)
            np.savez_compressed(self.path, **self.data)
            self.dirty = False


_cache = None


def embed(texts, task="RETRIEVAL_DOCUMENT"):
    """Trả về ma trận (n, EMBED_DIM) đã chuẩn hoá độ dài = 1, để tích vô hướng = cosine.

    task: RETRIEVAL_DOCUMENT cho đoạn/case trong kho, RETRIEVAL_QUERY cho câu hỏi.
    """
    global _cache
    from google.genai import types

    if _cache is None:
        _cache = _Cache()
    keys = [_cache.key(t, task) for t in texts]
    todo = [i for i, k in enumerate(keys) if k not in _cache.data]
    for s in range(0, len(todo), BATCH):
        idx = todo[s:s + BATCH]
        r = _retry(lambda: client().models.embed_content(
            model=EMBED_MODEL,
            contents=[texts[i] for i in idx],
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=EMBED_DIM),
        ))
        for i, e in zip(idx, r.embeddings):
            _cache.data[keys[i]] = np.asarray(e.values, dtype=np.float32)
        _cache.dirty = True
    _cache.save()
    M = np.stack([_cache.data[k] for k in keys]) if keys else np.zeros((0, EMBED_DIM), np.float32)
    # chiều < 3072 thì Gemini không tự chuẩn hoá
    return M / np.clip(np.linalg.norm(M, axis=1, keepdims=True), 1e-9, None)


# ---------------------------------------------------------------- LLM
def generate(prompt, system=None, temperature=0.2, json_mode=False):
    from google.genai import types

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    r = _retry(lambda: client().models.generate_content(model=LLM_MODEL, contents=prompt, config=cfg))
    text = (r.text or "").strip()
    return json.loads(text) if json_mode else text
