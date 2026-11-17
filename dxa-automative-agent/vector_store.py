"""Kho vector: dùng Qdrant (chế độ local, lưu trong index/qdrant, không cần chạy server).

Không cài qdrant-client thì tự dùng numpy (với 300 vector, numpy cũng đủ nhanh).
Muốn dùng Qdrant server thật: đặt QDRANT_URL=http://localhost:6333
"""
import os
from pathlib import Path

import numpy as np

INDEX = Path(__file__).parent / "index"


def _qdrant():
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return None
    url = os.getenv("QDRANT_URL")
    return QdrantClient(url=url) if url else QdrantClient(path=str(INDEX / "qdrant"))


class VectorStore:
    def __init__(self):
        self.q = _qdrant()
        self.backend = "qdrant" if self.q else "numpy"

    def put(self, name, vectors, payloads):
        """Ghi đè cả collection. id của điểm = thứ tự trong state (chunks/cases của dxa.py)."""
        vectors = np.asarray(vectors, dtype=np.float32)
        if self.q:
            from qdrant_client.models import Distance, PointStruct, VectorParams

            if self.q.collection_exists(name):
                self.q.delete_collection(name)
            self.q.create_collection(name, vectors_config=VectorParams(size=vectors.shape[1], distance=Distance.COSINE))
            pts = [PointStruct(id=i, vector=v.tolist(), payload=p) for i, (v, p) in enumerate(zip(vectors, payloads))]
            for s in range(0, len(pts), 256):
                self.q.upsert(name, points=pts[s:s + 256])
        else:
            INDEX.mkdir(exist_ok=True)
            np.save(INDEX / f"gemini_{name}.npy", vectors)

    def search(self, name, qvec, top=10):
        """Trả về [(id, cosine)], id là thứ tự trong state."""
        if self.q:
            res = self.q.query_points(name, query=np.asarray(qvec, dtype=np.float32).tolist(), limit=top)
            return [(int(p.id), float(p.score)) for p in res.points]
        M = np.load(INDEX / f"gemini_{name}.npy")
        s = M @ qvec
        order = np.argsort(-s)[:top]
        return [(int(i), float(s[i])) for i in order]

    def count(self, name):
        if self.q:
            return self.q.count(name).count if self.q.collection_exists(name) else 0
        p = INDEX / f"gemini_{name}.npy"
        return len(np.load(p)) if p.exists() else 0
