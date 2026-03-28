"""LLM-assisted verification with structured JSON output."""

from __future__ import annotations

import json
from typing import Any, Optional

from app.config import AppConfig
from app.llm_client import LLMClient, LLMClientError, optional_client
from app.models import Confidence, ContextPack, VerificationResult, VerifierSource


SYSTEM_PROMPT = """You are a senior Java backend reviewer. You ONLY output a single JSON object, no markdown.
Assess long-run operational risk conservatively. A finding is a candidate, not necessarily a bug.
JSON schema keys (all required):
{
  "confirmed": true | false | null,
  "confidence": "low" | "medium" | "high",
  "why_risky_long_term": string,
  "evidence_summary": string,
  "false_positive_possibility": string,
  "suggested_near_fix": string,
  "suggested_long_term_fix": string
}
Use null for confirmed when uncertain."""


def _clamp_conf(s: str) -> Confidence:
    s = (s or "medium").lower()
    if s == "high":
        return Confidence.HIGH
    if s == "low":
        return Confidence.LOW
    return Confidence.MEDIUM


def _parse_confirmed(v: Any) -> Optional[bool]:
    if v is True:
        return True
    if v is False:
        return False
    return None


def normalize_llm_payload(data: dict[str, Any]) -> VerificationResult:
    return VerificationResult(
        confirmed=_parse_confirmed(data.get("confirmed")),
        confidence=_clamp_conf(str(data.get("confidence", "medium"))),
        why_risky_long_term=str(data.get("why_risky_long_term", "")),
        evidence_summary=str(data.get("evidence_summary", "")),
        false_positive_possibility=str(data.get("false_positive_possibility", "")),
        suggested_near_fix=str(data.get("suggested_near_fix", "")),
        suggested_long_term_fix=str(data.get("suggested_long_term_fix", "")),
        verifier_source=VerifierSource.LLM,
        raw=data,
    )


def build_user_prompt(pack: ContextPack, config: AppConfig) -> str:
    lines = pack.nearby_lines.splitlines()
    cap = config.llm_max_context_lines
    if len(lines) > cap:
        lines = lines[:cap]
    nearby = "\n".join(lines)
    refs = "\n".join(pack.project_references[: config.llm_max_project_references])
    payload = {
        "risk_id": pack.risk_rule.id,
        "risk_name": pack.risk_rule.name,
        "risk_description": pack.risk_rule.description,
        "long_run_impact_catalog": pack.risk_rule.long_run_impact,
        "llm_questions": pack.risk_rule.llm_questions,
        "file_path": pack.file_path,
        "line_range": [pack.line_start, pack.line_end],
        "snippet": pack.snippet[:4000],
        "enclosing_class": pack.enclosing_class,
        "enclosing_method": pack.enclosing_method,
        "annotations": pack.annotations_in_scope,
        "inferred_clues": pack.inferred_clues,
        "inference_notes": pack.inference_notes,
        "nearby_lines_capped": nearby[:8000],
        "optional_project_reference_paths": refs,
    }
    return json.dumps(payload, ensure_ascii=False)


def verify_with_llm(config: AppConfig, pack: ContextPack) -> Optional[VerificationResult]:
    client = optional_client(config)
    if client is None:
        return None
    user = build_user_prompt(pack, config)
    try:
        data = client.chat_json(SYSTEM_PROMPT, user)
    except LLMClientError:
        return None
    return normalize_llm_payload(data)
