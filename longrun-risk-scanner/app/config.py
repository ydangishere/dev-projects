"""Load configuration from environment and optional .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _find_project_root() -> Path:
    """Directory containing rules/ and scans/ (parent of app/)."""
    here = Path(__file__).resolve().parent
    return here.parent


def _load_dotenv() -> None:
    root = _find_project_root()
    env_path = root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    load_dotenv(override=False)


@dataclass(frozen=True)
class AppConfig:
    rules_path: Path
    scans_dir: Path
    db_path: Path

    llm_enabled: bool
    llm_provider: str
    llm_api_base: str
    llm_model: str
    llm_api_key_env: str
    llm_temperature: float
    llm_max_context_lines: int
    llm_max_project_references: int

    @property
    def llm_api_key(self) -> Optional[str]:
        name = self.llm_api_key_env.strip()
        if not name:
            return None
        v = os.environ.get(name, "").strip()
        return v or None


def load_config() -> AppConfig:
    _load_dotenv()
    root = _find_project_root()

    def _bool(key: str, default: bool) -> bool:
        raw = os.environ.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def _int(key: str, default: int) -> int:
        raw = os.environ.get(key)
        if raw is None or not raw.strip():
            return default
        try:
            return int(raw.strip())
        except ValueError:
            return default

    def _float(key: str, default: float) -> float:
        raw = os.environ.get(key)
        if raw is None or not raw.strip():
            return default
        try:
            return float(raw.strip())
        except ValueError:
            return default

    rules = Path(os.environ.get("RULES_PATH", str(root / "rules" / "risks.yaml")))
    if not rules.is_absolute():
        rules = (root / rules).resolve()

    scans = Path(os.environ.get("SCANS_DIR", str(root / "scans")))
    if not scans.is_absolute():
        scans = (root / scans).resolve()

    db = Path(os.environ.get("DB_PATH", str(root / "scans" / "longrun.db")))
    if not db.is_absolute():
        db = (root / db).resolve()

    return AppConfig(
        rules_path=rules,
        scans_dir=scans,
        db_path=db,
        llm_enabled=_bool("LLM_ENABLED", False),
        llm_provider=os.environ.get("LLM_PROVIDER", "openai").strip() or "openai",
        llm_api_base=os.environ.get("LLM_API_BASE", "https://api.openai.com/v1").strip().rstrip("/"),
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        llm_api_key_env=os.environ.get("LLM_API_KEY_ENV", "OPENAI_API_KEY").strip(),
        llm_temperature=_float("LLM_TEMPERATURE", 0.1),
        llm_max_context_lines=max(20, _int("LLM_MAX_CONTEXT_LINES", 120)),
        llm_max_project_references=max(1, _int("LLM_MAX_PROJECT_REFERENCES", 8)),
    )
