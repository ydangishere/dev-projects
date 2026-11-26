"""Pluggable LLM providers.

* offline (default): no model at all; the pipeline uses regex extraction and templates.
* gemini: Google Gemini REST API (needs GEMINI_API_KEY).
* openai: any OpenAI-compatible /chat/completions endpoint, including an on-premise
  vLLM/Ollama server, which is the usual choice for a bank (OPENAI_BASE_URL, OPENAI_API_KEY).

Only the Python standard library is used, so the offline demo has no extra dependency.
The model is never trusted with numbers or decisions: callers validate every output.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str = "offline"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> LLMConfig:
        provider = os.getenv("LLM_PROVIDER", "offline").strip().lower()
        if provider == "gemini":
            return cls(provider, os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                       os.getenv("GEMINI_API_KEY", ""),
                       "https://generativelanguage.googleapis.com/v1beta")
        if provider == "openai":
            return cls(provider, os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                       os.getenv("OPENAI_API_KEY", ""),
                       os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"))
        return cls("offline")

    @property
    def enabled(self) -> bool:
        if self.provider == "gemini":
            return bool(self.api_key)
        if self.provider == "openai":
            # A local OpenAI-compatible server (vLLM, Ollama) may not need a key.
            return bool(self.api_key) or "api.openai.com" not in self.base_url
        return False


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json", **headers},
                                     method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc


def complete_json(config: LLMConfig, system: str, user: str) -> dict:
    """Ask the configured model for a JSON object. Raises LLMError on any failure."""
    if not config.enabled:
        raise LLMError("No LLM provider configured")
    if config.provider == "gemini":
        url = f"{config.base_url}/models/{config.model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        data = _post_json(url, payload, {"x-goog-api-key": config.api_key}, config.timeout)
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected Gemini response: {str(data)[:200]}") from exc
    else:
        url = f"{config.base_url}/chat/completions"
        payload = {
            "model": config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        data = _post_json(url, payload, headers, config.timeout)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected OpenAI-compatible response: {str(data)[:200]}") from exc
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError("Model did not return valid JSON") from exc
    if not isinstance(result, dict):
        raise LLMError("Model JSON is not an object")
    return result
