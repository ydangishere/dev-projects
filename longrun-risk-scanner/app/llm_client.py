"""OpenAI-compatible chat completions client (swappable provider via base URL)."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import AppConfig


class LLMClientError(Exception):
    pass


class LLMClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        key = self._config.llm_api_key
        if not key:
            raise LLMClientError("No API key configured")

        url = f"{self._config.llm_api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._config.llm_model,
            "temperature": self._config.llm_temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError as e:
            raise LLMClientError(str(e)) from e

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMClientError("Malformed API response") from e

        import json

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMClientError(f"Invalid JSON from model: {e}") from e


def optional_client(config: AppConfig) -> Optional[LLMClient]:
    if not config.llm_enabled or not config.llm_api_key:
        return None
    return LLMClient(config)
