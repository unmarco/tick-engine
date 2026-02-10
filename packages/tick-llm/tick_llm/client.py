"""LLM client protocol and mock implementation."""
from __future__ import annotations

import random as _random_mod
import time
from typing import Callable, Protocol, runtime_checkable


class LLMError(Exception):
    """Exception raised by LLM client operations."""


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM client implementations.

    Implementations make blocking calls (invoked inside a thread pool worker).
    Any exception may be raised on failure -- the system catches all exceptions
    and routes them through error handling.
    """

    def query(self, system_prompt: str, user_message: str) -> str:
        """Send a prompt to an LLM and return the response string."""
        ...


class MockClient:
    """Deterministic LLM client for testing.

    Conforms to the LLMClient protocol. Supports configurable response
    mappings, latency simulation, and error injection.

    Args:
        responses: A dict mapping (system_prompt, user_message) tuples to
            response strings, OR a callable (str, str) -> str for dynamic
            responses.
        latency: Simulated delay in seconds before returning (default 0.0).
        error_rate: Probability of raising an exception (0.0--1.0, default 0.0).
        error_exception: The exception instance to raise on simulated error.
            Defaults to LLMError("mock error") if None.
    """

    def __init__(
        self,
        responses: dict[tuple[str, str], str] | Callable[[str, str], str],
        latency: float = 0.0,
        error_rate: float = 0.0,
        error_exception: BaseException | None = None,
    ) -> None:
        self._responses = responses
        self._latency = latency
        self._error_rate = error_rate
        self._error_exception = (
            error_exception if error_exception is not None else LLMError("mock error")
        )
        # Per-instance RNG for thread safety (no shared state).
        self._rng = _random_mod.Random()

    def query(self, system_prompt: str, user_message: str) -> str:
        """Return a mock response, optionally simulating latency and errors."""
        if self._error_rate > 0.0 and self._rng.random() < self._error_rate:
            raise self._error_exception

        if self._latency > 0.0:
            time.sleep(self._latency)

        if callable(self._responses) and not isinstance(self._responses, dict):
            return self._responses(system_prompt, user_message)

        return self._responses.get((system_prompt, user_message), "{}")
