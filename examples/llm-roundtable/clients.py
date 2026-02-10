"""LM Studio client adapters using stdlib urllib.

Two classes implementing the LLMClient protocol:
- LMStudioOpenAIClient: OpenAI-compatible /v1/chat/completions endpoint
- LMStudioAnthropicClient: Anthropic-compatible /v1/messages endpoint

Plus a list_models() helper for auto-detection.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error


class LMStudioOpenAIClient:
    """LLM client for LM Studio's OpenAI-compatible endpoint.

    Uses POST /v1/chat/completions with the chat messages format.
    """

    def __init__(
        self,
        model: str = "default",
        base_url: str = "http://localhost:1234",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens

    def query(self, system_prompt: str, user_message: str) -> str:
        """Send a chat completion request and return the response text."""
        payload = json.dumps({
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        return body["choices"][0]["message"]["content"]


class LMStudioAnthropicClient:
    """LLM client for LM Studio's Anthropic-compatible endpoint.

    Uses POST /v1/messages with the Anthropic messages format.
    """

    def __init__(
        self,
        model: str = "default",
        base_url: str = "http://localhost:1234",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens

    def query(self, system_prompt: str, user_message: str) -> str:
        """Send an Anthropic-format messages request and return the response text."""
        payload = json.dumps({
            "model": self._model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": "lm-studio",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        return body["content"][0]["text"]


def list_models(base_url: str = "http://localhost:1234") -> list[dict[str, str]]:
    """Fetch available models from LM Studio's /v1/models endpoint.

    Returns a list of dicts with at least an 'id' key each.
    Raises urllib.error.URLError if LM Studio is unreachable.
    """
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/models",
        headers={"Content-Type": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    return body.get("data", [])
