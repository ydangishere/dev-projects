"""Cache kết quả để tránh gọi API lặp lại."""
import hashlib
import json
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent.parent / "cache"


def _hash_key(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()


def get(cache_key: str, subdir: str = "") -> Optional[str]:
    """Lấy từ cache nếu có."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sub = Path(subdir) if subdir else Path(".")
    path = CACHE_DIR / sub / f"{_hash_key(cache_key)}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("value")
    return None


def set(cache_key: str, value: str, subdir: str = "") -> None:
    """Lưu vào cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sub = Path(subdir) if subdir else Path(".")
    (CACHE_DIR / sub).mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / sub / f"{_hash_key(cache_key)}.json"
    path.write_text(json.dumps({"value": value}, ensure_ascii=False), encoding="utf-8")


def get_file(cache_key: str, subdir: str, ext: str) -> Optional[Path]:
    """Lấy path file đã cache (mp3, mp4...)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sub = Path(subdir) if subdir else Path(".")
    path = CACHE_DIR / sub / f"{_hash_key(cache_key)}.{ext}"
    return path if path.exists() else None


def set_file(cache_key: str, source_path: Path, subdir: str) -> Path:
    """Copy file vào cache, trả về path mới."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sub = Path(subdir) if subdir else Path(".")
    (CACHE_DIR / sub).mkdir(parents=True, exist_ok=True)
    ext = source_path.suffix.lstrip(".")
    dest = CACHE_DIR / sub / f"{_hash_key(cache_key)}.{ext}"
    import shutil
    shutil.copy(source_path, dest)
    return dest
