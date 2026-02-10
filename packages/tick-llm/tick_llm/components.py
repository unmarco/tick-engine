"""ECS component for LLM-driven entities."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMAgent:
    """Marks an entity as LLM-driven and tracks query state.

    Attributes:
        role: Name of the role definition in LLMManager.
        personality: Name of the personality definition in LLMManager.
        context: Name of the context template in LLMManager.
        parser: Name of the parser in LLMManager; empty string uses default
            JSON parser.
        query_interval: Minimum ticks between queries. 0 means query as fast
            as rate limits allow.
        priority: Query priority; higher values are queried first when
            rate-limited.
        last_query_tick: Tick number of most recent query dispatch.
        pending: True while a query is in flight.
        consecutive_errors: Number of consecutive query failures.
        max_retries: Max consecutive errors before cooldown.
        cooldown_ticks: Ticks to wait after hitting max_retries.
        cooldown_until: Tick number when cooldown expires.
    """

    role: str
    personality: str
    context: str
    parser: str = ""
    query_interval: int = 100
    priority: int = 0
    last_query_tick: int = 0
    pending: bool = False
    consecutive_errors: int = 0
    max_retries: int = 3
    cooldown_ticks: int = 200
    cooldown_until: int = 0
