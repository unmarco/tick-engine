"""LLM configuration dataclass."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Immutable configuration for the LLM strategic layer.

    Attributes:
        max_queries_per_tick: Maximum new queries dispatched per tick.
        max_queries_per_second: Sliding-window rate limit across ticks.
        thread_pool_size: ThreadPoolExecutor max workers.
        query_timeout: Seconds before a pending query is considered timed out.
    """

    max_queries_per_tick: int = 1
    max_queries_per_second: int = 5
    thread_pool_size: int = 4
    query_timeout: float = 30.0
