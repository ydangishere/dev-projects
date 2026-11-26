"""Language-model access through LiteLLM.

One configuration string chooses the model, so the same code runs against:
* a self-hosted Qwen via Ollama:   LLM_MODEL=ollama_chat/qwen2.5:7b  LLM_API_BASE=http://ollama:11434
* Google Gemini:                   LLM_MODEL=gemini/gemini-2.5-flash  GEMINI_API_KEY=...
* the bank's LiteLLM proxy:        LLM_MODEL=litellm_proxy/copilot   LLM_API_BASE=http://litellm:4000
  (the proxy adds rate limits, budgets, key management and model fallbacks centrally).

Unset LLM_MODEL means offline mode: no model is called at all.
The model is never trusted with numbers or decisions; callers validate every output.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from .observability import LLM_CALLS, LLM_SECONDS, LLM_TOKENS, timer, traced


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    model: str = ""
    api_base: str = ""
    api_key: str = ""
    fallback_model: str = ""
    timeout: float = 90.0
    max_retries: int = 1

    @classmethod
    def from_env(cls) -> LLMConfig:
        model = os.getenv("LLM_MODEL", "").strip()
        legacy = os.getenv("LLM_PROVIDER", "").strip().lower()
        if not model and legacy == "gemini":  # backwards compatible with the first version
            model = "gemini/" + os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not model and legacy == "openai":
            model = "openai/" + os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        return cls(
            model=model,
            api_base=os.getenv("LLM_API_BASE", os.getenv("OPENAI_BASE_URL", "") if legacy == "openai" else ""),
            api_key=os.getenv("LLM_API_KEY", ""),
            fallback_model=os.getenv("LLM_FALLBACK_MODEL", ""),
            timeout=float(os.getenv("LLM_TIMEOUT", "90")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.model)

    @property
    def provider(self) -> str:
        return self.model.split("/", 1)[0] if self.model else "offline"


def parse_json_object(text: str) -> dict:
    """Small local models often wrap JSON in ``` fences or add a sentence; recover the object."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise LLMError("Model did not return JSON") from None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError("Model returned malformed JSON") from exc
    if not isinstance(value, dict):
        raise LLMError("Model JSON is not an object")
    return value


@traced("llm-call", as_type="generation")
def complete_json(config: LLMConfig, system: str, user: str, purpose: str = "general") -> dict:
    """Ask the configured model for a JSON object. Raises LLMError on any failure."""
    if not config.enabled:
        raise LLMError("No LLM configured")
    try:
        import litellm
    except ImportError as exc:
        raise LLMError("litellm is not installed") from exc
    kwargs = {
        "model": config.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "timeout": config.timeout,
        "num_retries": config.max_retries,
    }
    if config.api_base:
        kwargs["api_base"] = config.api_base
    if config.api_key:
        kwargs["api_key"] = config.api_key
    if config.fallback_model:
        kwargs["fallbacks"] = [config.fallback_model]
    try:
        with timer(LLM_SECONDS, purpose=purpose):
            response = litellm.completion(**kwargs)
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        if usage:
            LLM_TOKENS.labels(purpose=purpose, kind="prompt").inc(getattr(usage, "prompt_tokens", 0) or 0)
            LLM_TOKENS.labels(purpose=purpose, kind="completion").inc(getattr(usage, "completion_tokens", 0) or 0)
        result = parse_json_object(text)
    except LLMError:
        LLM_CALLS.labels(purpose=purpose, outcome="bad_json").inc()
        raise
    except Exception as exc:  # noqa: BLE001 - provider errors vary widely
        LLM_CALLS.labels(purpose=purpose, outcome="error").inc()
        raise LLMError(f"LLM request failed: {type(exc).__name__}: {str(exc)[:200]}") from exc
    LLM_CALLS.labels(purpose=purpose, outcome="ok").inc()
    return result
