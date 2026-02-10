"""LLM system for managing async queries within the tick engine loop.

Provides the LLMSystem class and make_llm_system() factory. The system
manages the full lifecycle of asynchronous LLM queries: harvesting completed
futures, detecting timeouts, and dispatching new queries to a thread pool.
"""
from __future__ import annotations

import sys
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tick_ai.components import Blackboard

from tick_llm.components import LLMAgent
from tick_llm.manager import LLMManager, ParserFn
from tick_llm.parsers import default_json_parser

if TYPE_CHECKING:
    from tick import TickContext, World


@dataclass(frozen=True)
class _PendingQuery:
    """Internal record of an in-flight LLM query."""

    eid: int
    future: Future[str]
    submitted_at: float
    submitted_tick: int


class LLMSystem:
    """Async LLM query system for the tick engine.

    Callable object satisfying the tick engine System protocol. Manages
    query dispatch to a ThreadPoolExecutor, response harvesting, timeout
    detection, rate limiting, and error handling.

    Use ``make_llm_system(manager)`` to create an instance.
    """

    def __init__(self, manager: LLMManager) -> None:
        self._manager = manager
        self._executor = ThreadPoolExecutor(
            max_workers=manager.config.thread_pool_size,
        )
        self._pending: dict[int, _PendingQuery] = {}
        self._dispatch_times: deque[float] = deque()
        self._shutdown: bool = False

    def __call__(self, world: World, ctx: TickContext) -> None:
        """Execute one tick of the LLM system.

        Three phases in order: harvest completed futures, check timeouts,
        dispatch new queries for eligible entities.
        """
        if self._shutdown:
            return

        self._phase_harvest(world, ctx)
        self._phase_timeout(world, ctx)
        self._phase_dispatch(world, ctx)

    def shutdown(self) -> None:
        """Shut down the thread pool and discard all pending queries.

        After shutdown, subsequent ``__call__`` invocations are no-ops.
        Callers should invoke this when the engine stops.
        """
        self._shutdown = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._pending.clear()

    # ------------------------------------------------------------------
    # Phase 1: Harvest
    # ------------------------------------------------------------------

    def _phase_harvest(self, world: World, ctx: TickContext) -> None:
        """Check all pending futures for completion and process results."""
        for eid in list(self._pending):
            pq = self._pending[eid]
            if not pq.future.done():
                continue

            # Remove from pending regardless of outcome.
            del self._pending[eid]

            # If entity no longer has LLMAgent, silently discard.
            if not world.has(eid, LLMAgent):
                continue
            agent = world.get(eid, LLMAgent)

            # If entity no longer has Blackboard, silently discard.
            if not world.has(eid, Blackboard):
                continue
            bb = world.get(eid, Blackboard)

            agent.pending = False

            # Check for exception from the future.
            exc = pq.future.exception()
            if exc is not None:
                agent.consecutive_errors += 1
                if agent.consecutive_errors >= agent.max_retries:
                    agent.cooldown_until = ctx.tick_number + agent.cooldown_ticks
                self._fire_on_error(
                    eid, "query_error", str(exc), ctx.tick_number,
                )
                continue

            # Successful result.
            response = pq.future.result()
            latency = time.monotonic() - pq.submitted_at

            # Parse the response.
            parser_fn = self._resolve_parser(agent)
            try:
                parser_fn(response, bb)
            except Exception as parse_exc:
                agent.consecutive_errors += 1
                if agent.consecutive_errors >= agent.max_retries:
                    agent.cooldown_until = (
                        ctx.tick_number + agent.cooldown_ticks
                    )
                self._fire_on_error(
                    eid, "parse_error", str(parse_exc), ctx.tick_number,
                )
                continue

            # Success -- reset error counter and fire response callback.
            agent.consecutive_errors = 0
            self._fire_on_response(
                eid, latency, len(response), ctx.tick_number,
            )

    # ------------------------------------------------------------------
    # Phase 2: Timeout
    # ------------------------------------------------------------------

    def _phase_timeout(self, world: World, ctx: TickContext) -> None:
        """Cancel queries that have exceeded the configured timeout."""
        timeout = self._manager.config.query_timeout
        now = time.monotonic()

        for eid in list(self._pending):
            pq = self._pending[eid]
            if now - pq.submitted_at > timeout:
                pq.future.cancel()
                del self._pending[eid]

                if world.has(eid, LLMAgent):
                    agent = world.get(eid, LLMAgent)
                    agent.pending = False
                    agent.consecutive_errors += 1
                    if agent.consecutive_errors >= agent.max_retries:
                        agent.cooldown_until = (
                            ctx.tick_number + agent.cooldown_ticks
                        )

                self._fire_on_error(
                    eid,
                    "timeout",
                    f"Query timed out after {timeout}s",
                    ctx.tick_number,
                )

    # ------------------------------------------------------------------
    # Phase 3: Dispatch
    # ------------------------------------------------------------------

    def _phase_dispatch(self, world: World, ctx: TickContext) -> None:
        """Find eligible entities and submit queries to the thread pool."""
        client = self._manager.client
        if client is None:
            # Fire on_error once per tick if any LLMAgent entities exist.
            for eid, (_agent,) in world.query(LLMAgent):
                self._fire_on_error(
                    eid,
                    "no_client",
                    "No LLM client registered",
                    ctx.tick_number,
                )
                break  # only fire once
            return

        # Prune the sliding window of dispatch timestamps.
        cutoff = time.monotonic() - 1.0
        while self._dispatch_times and self._dispatch_times[0] < cutoff:
            self._dispatch_times.popleft()

        # Collect eligible entities.
        eligible: list[tuple[int, LLMAgent]] = []
        for eid, (agent,) in world.query(LLMAgent):
            if agent.pending:
                continue
            if agent.cooldown_until > ctx.tick_number:
                continue
            if (
                agent.query_interval > 0
                and ctx.tick_number - agent.last_query_tick < agent.query_interval
            ):
                continue
            eligible.append((eid, agent))

        # Sort by priority descending, eid ascending for determinism.
        eligible.sort(key=lambda x: (-x[1].priority, x[0]))

        dispatched = 0
        max_per_tick = self._manager.config.max_queries_per_tick
        max_per_second = self._manager.config.max_queries_per_second

        for eid, agent in eligible:
            if dispatched >= max_per_tick:
                break
            if len(self._dispatch_times) >= max_per_second:
                break

            # Validate that all referenced definition names exist.
            missing: list[str] = []
            if self._manager.role(agent.role) is None:
                missing.append(f"role '{agent.role}'")
            if self._manager.personality(agent.personality) is None:
                missing.append(f"personality '{agent.personality}'")
            if self._manager.context(agent.context) is None:
                missing.append(f"context '{agent.context}'")
            if agent.parser and self._manager.parser(agent.parser) is None:
                missing.append(f"parser '{agent.parser}'")

            if missing:
                # Configuration error -- fire on_error, do NOT set pending or
                # increment consecutive_errors.
                self._fire_on_error(
                    eid,
                    "missing_definition",
                    f"Missing: {', '.join(missing)}",
                    ctx.tick_number,
                )
                continue

            # Entity must have a Blackboard for the parser to write to.
            if not world.has(eid, Blackboard):
                continue  # skip silently

            # Assemble prompt.
            prompt = self._manager.assemble_prompt(world, eid, agent)
            if prompt is None:
                # Shouldn't happen since we validated above, but handle
                # gracefully rather than crashing.
                continue

            system_prompt, user_message = prompt

            # Submit to thread pool.
            future: Future[str] = self._executor.submit(
                client.query, system_prompt, user_message,
            )
            now_ts = time.monotonic()
            self._pending[eid] = _PendingQuery(
                eid=eid,
                future=future,
                submitted_at=now_ts,
                submitted_tick=ctx.tick_number,
            )
            self._dispatch_times.append(now_ts)

            agent.pending = True
            agent.last_query_tick = ctx.tick_number

            prompt_size = len(system_prompt) + len(user_message)
            self._fire_on_query(eid, prompt_size, ctx.tick_number)

            dispatched += 1

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_parser(self, agent: LLMAgent) -> ParserFn:
        """Return the parser function for the given agent.

        If the agent's parser name is empty, returns the default JSON parser.
        Otherwise returns the named parser from the manager (which has already
        been validated to exist at dispatch time).
        """
        if not agent.parser:
            return default_json_parser
        fn = self._manager.parser(agent.parser)
        # Should never be None because we validate at dispatch, but be safe.
        assert fn is not None, f"Parser '{agent.parser}' missing at harvest"
        return fn

    def _fire_on_query(
        self, eid: int, prompt_size: int, tick: int,
    ) -> None:
        """Fire on_query callbacks with error isolation."""
        for cb in self._manager._on_query:
            try:
                cb(eid, prompt_size, tick)
            except Exception:
                print(
                    f"tick-llm: on_query callback error: {sys.exc_info()[1]}",
                    file=sys.stderr,
                )

    def _fire_on_response(
        self, eid: int, latency: float, response_size: int, tick: int,
    ) -> None:
        """Fire on_response callbacks with error isolation."""
        for cb in self._manager._on_response:
            try:
                cb(eid, latency, response_size, tick)
            except Exception:
                print(
                    f"tick-llm: on_response callback error: {sys.exc_info()[1]}",
                    file=sys.stderr,
                )

    def _fire_on_error(
        self, eid: int, error_type: str, error_msg: str, tick: int,
    ) -> None:
        """Fire on_error callbacks with error isolation.

        Exceptions in on_error callbacks are logged and swallowed.
        """
        for cb in self._manager._on_error:
            try:
                cb(eid, error_type, error_msg, tick)
            except Exception:
                print(
                    f"tick-llm: on_error callback error: {sys.exc_info()[1]}",
                    file=sys.stderr,
                )


def make_llm_system(manager: LLMManager) -> LLMSystem:
    """Create an LLM system from a manager.

    Returns an ``LLMSystem`` instance that can be passed to
    ``engine.add_system()``. The system creates a ThreadPoolExecutor
    internally and manages async LLM query lifecycles.

    Call ``system.shutdown()`` when the engine stops to clean up the
    thread pool.
    """
    return LLMSystem(manager)
