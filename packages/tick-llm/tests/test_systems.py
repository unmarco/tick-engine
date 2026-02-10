"""Tests for LLMSystem and make_llm_system factory."""
import time

import pytest

from tick import Engine
from tick_ai.components import Blackboard
from tick_llm import (
    LLMAgent,
    LLMConfig,
    LLMManager,
    LLMSystem,
    MockClient,
    make_llm_system,
)
from tick_llm.client import LLMError


def _setup_basic() -> LLMManager:
    """Create a minimal LLM setup for testing."""
    config = LLMConfig(
        max_queries_per_tick=5, max_queries_per_second=50, query_timeout=5.0
    )
    manager = LLMManager(config=config)
    manager.define_role("test_role", "You are a test agent.")
    manager.define_personality("test_personality", "You are helpful.")
    manager.define_context("test_context", lambda world, eid: "What should I do?")
    client = MockClient(responses={})  # returns "{}" for all queries
    manager.register_client(client)
    return manager


class TestSystemConstruction:
    """Test system construction and basic properties."""

    def test_make_llm_system_returns_llm_system(self) -> None:
        manager = _setup_basic()
        system = make_llm_system(manager)
        assert isinstance(system, LLMSystem)
        system.shutdown()

    def test_system_callable(self) -> None:
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        engine.add_system(system)
        engine.step()
        system.shutdown()

    def test_shutdown_makes_system_noop(self) -> None:
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)
        system.shutdown()
        engine.step()
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert agent.last_query_tick == 0


class TestDispatch:
    """Test query dispatch logic."""

    def test_dispatch_eligible_entity(self) -> None:
        """Entity with query_interval=1 dispatches on tick 1 (1-0>=1)."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Tick 1: eligible (1 - 0 = 1 >= 1)
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True
        assert agent.last_query_tick == 1

        system.shutdown()

    def test_dispatch_respects_query_interval(self) -> None:
        """Entity with query_interval=5 not dispatched until tick 5."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=5,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Ticks 1-4: not eligible (tick - 0 < 5)
        for _ in range(4):
            engine.step()
            agent = engine.world.get(eid, LLMAgent)
            assert agent.pending is False

        # Tick 5: eligible (5 - 0 = 5 >= 5)
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True

        system.shutdown()

    def test_dispatch_skips_pending_entity(self) -> None:
        """Entity with pending=True is not dispatched again."""
        manager = _setup_basic()
        # Use high-latency client so future stays pending across ticks
        client = MockClient(responses={}, latency=1.0)
        manager.register_client(client)
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Tick 1: dispatch
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True
        last_tick = agent.last_query_tick

        # Tick 2: should skip (still pending due to latency)
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.last_query_tick == last_tick

        system.shutdown()

    def test_dispatch_skips_entity_in_cooldown(self) -> None:
        """Entity with cooldown_until > tick is skipped."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        agent = LLMAgent(
            role="test_role",
            personality="test_personality",
            context="test_context",
            query_interval=1,
        )
        agent.cooldown_until = 10
        engine.world.attach(eid, agent)
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Ticks 1-9: cooldown (10 > tick_number)
        for _ in range(9):
            engine.step()
            agent = engine.world.get(eid, LLMAgent)
            assert agent.pending is False

        # Tick 10: cooldown expired (10 > 10 is False), dispatch
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True

        system.shutdown()

    def test_dispatch_query_interval_zero(self) -> None:
        """Entity with query_interval=0 is eligible every tick."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=0,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True

        system.shutdown()

    def test_dispatch_priority_ordering(self) -> None:
        """Higher priority entities dispatched first."""
        config = LLMConfig(max_queries_per_tick=1, max_queries_per_second=50)
        manager = LLMManager(config=config)
        manager.define_role("test_role", "You are a test agent.")
        manager.define_personality("test_personality", "You are helpful.")
        manager.define_context("test_context", lambda w, e: "Act.")
        manager.register_client(MockClient(responses={}))
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eid_low = engine.world.spawn()
        engine.world.attach(
            eid_low,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
                priority=1,
            ),
        )
        engine.world.attach(eid_low, Blackboard())

        eid_high = engine.world.spawn()
        engine.world.attach(
            eid_high,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
                priority=10,
            ),
        )
        engine.world.attach(eid_high, Blackboard())
        engine.add_system(system)

        # Tick 1: both eligible, only 1 per tick, high priority wins
        engine.step()
        assert engine.world.get(eid_high, LLMAgent).pending is True
        assert engine.world.get(eid_low, LLMAgent).pending is False

        system.shutdown()

    def test_dispatch_eid_tiebreaking(self) -> None:
        """Same priority, lower eid dispatched first."""
        config = LLMConfig(max_queries_per_tick=1, max_queries_per_second=50)
        manager = LLMManager(config=config)
        manager.define_role("test_role", "You are a test agent.")
        manager.define_personality("test_personality", "You are helpful.")
        manager.define_context("test_context", lambda w, e: "Act.")
        manager.register_client(MockClient(responses={}))
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eid1 = engine.world.spawn()
        eid2 = engine.world.spawn()

        engine.world.attach(
            eid2,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
                priority=5,
            ),
        )
        engine.world.attach(eid2, Blackboard())

        engine.world.attach(
            eid1,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
                priority=5,
            ),
        )
        engine.world.attach(eid1, Blackboard())
        engine.add_system(system)

        engine.step()
        assert engine.world.get(eid1, LLMAgent).pending is True
        assert engine.world.get(eid2, LLMAgent).pending is False

        system.shutdown()

    def test_dispatch_max_queries_per_tick(self) -> None:
        """Only max_queries_per_tick dispatched per tick."""
        config = LLMConfig(max_queries_per_tick=2, max_queries_per_second=50)
        manager = LLMManager(config=config)
        manager.define_role("test_role", "You are a test agent.")
        manager.define_personality("test_personality", "You are helpful.")
        manager.define_context("test_context", lambda w, e: "Act.")
        manager.register_client(MockClient(responses={}))
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eids = []
        for _ in range(3):
            eid = engine.world.spawn()
            engine.world.attach(
                eid,
                LLMAgent(
                    role="test_role",
                    personality="test_personality",
                    context="test_context",
                    query_interval=1,
                ),
            )
            engine.world.attach(eid, Blackboard())
            eids.append(eid)
        engine.add_system(system)

        # Tick 1: all 3 eligible, only 2 dispatched
        engine.step()
        pending_count = sum(
            1 for e in eids if engine.world.get(e, LLMAgent).pending
        )
        assert pending_count == 2

        system.shutdown()

    def test_dispatch_max_queries_per_second(self) -> None:
        """Sliding window rate limit works."""
        config = LLMConfig(max_queries_per_tick=10, max_queries_per_second=3)
        manager = LLMManager(config=config)
        manager.define_role("test_role", "You are a test agent.")
        manager.define_personality("test_personality", "You are helpful.")
        manager.define_context("test_context", lambda w, e: "Act.")
        manager.register_client(MockClient(responses={}))
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eids = []
        for _ in range(5):
            eid = engine.world.spawn()
            engine.world.attach(
                eid,
                LLMAgent(
                    role="test_role",
                    personality="test_personality",
                    context="test_context",
                    query_interval=1,
                ),
            )
            engine.world.attach(eid, Blackboard())
            eids.append(eid)
        engine.add_system(system)

        # Tick 1: 5 eligible, max_per_second=3
        engine.step()
        pending_count = sum(
            1 for e in eids if engine.world.get(e, LLMAgent).pending
        )
        assert pending_count == 3

        system.shutdown()


class TestHarvest:
    """Test response harvesting and processing."""

    def test_harvest_successful_response(self) -> None:
        """Response parsed, Blackboard updated, consecutive_errors reset."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=2,  # dispatch tick 2, harvest tick 3 (no re-dispatch)
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch
        engine.step()  # tick 3: harvest

        agent = engine.world.get(eid, LLMAgent)
        bb = engine.world.get(eid, Blackboard)
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert "strategy" in bb.data

        system.shutdown()

    def test_harvest_fires_on_response_callback(self) -> None:
        """on_response callback fires with eid, latency, response_size, tick."""
        manager = _setup_basic()
        calls: list[tuple[int, float, int, int]] = []

        def on_response(eid: int, latency: float, size: int, tick: int) -> None:
            calls.append((eid, latency, size, tick))

        manager.on_response(on_response)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=2,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch
        engine.step()  # tick 3: harvest

        assert len(calls) == 1
        assert calls[0][0] == eid
        assert isinstance(calls[0][1], float)  # latency
        assert isinstance(calls[0][2], int)    # response_size
        assert calls[0][3] == 3                # tick number

        system.shutdown()

    def test_harvest_query_error_increments_consecutive_errors(self) -> None:
        """MockClient error increments consecutive_errors."""
        manager = _setup_basic()
        client = MockClient(responses={}, error_rate=1.0)
        manager.register_client(client)
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=2,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch (error in pool)
        engine.step()  # tick 3: harvest error

        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert agent.consecutive_errors == 1

        system.shutdown()

    def test_harvest_fires_on_error_on_failure(self) -> None:
        """on_error fires with error details on query failure."""
        manager = _setup_basic()
        client = MockClient(responses={}, error_rate=1.0)
        manager.register_client(client)
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=2,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch
        engine.step()  # tick 3: harvest error

        assert len(calls) == 1
        assert calls[0][0] == eid
        assert calls[0][1] == "query_error"
        assert "mock error" in calls[0][2]

        system.shutdown()

    def test_harvest_parse_error_increments_errors(self) -> None:
        """Parser raises, consecutive_errors++, on_error fires."""
        manager = _setup_basic()

        def bad_parser(response: str, blackboard: Blackboard) -> None:
            raise ValueError("parse failed")

        manager.define_parser("bad_parser", bad_parser)
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                parser="bad_parser",
                query_interval=2,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch
        engine.step()  # tick 3: harvest parse error

        agent = engine.world.get(eid, LLMAgent)
        assert agent.consecutive_errors == 1
        assert len(calls) == 1
        assert calls[0][1] == "parse_error"

        system.shutdown()

    def test_harvest_despawned_entity_silently_discarded(self) -> None:
        """Despawn entity while query pending, response silently discarded."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: dispatch
        engine.world.despawn(eid)
        engine.step()  # tick 2: harvest (entity gone, discard)

        assert not engine.world.has(eid, LLMAgent)
        system.shutdown()

    def test_harvest_detached_agent_silently_discarded(self) -> None:
        """Detach LLMAgent while query pending, silently discarded."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: dispatch
        engine.world.detach(eid, LLMAgent)
        engine.step()  # tick 2: harvest (agent gone, discard)

        assert not engine.world.has(eid, LLMAgent)
        system.shutdown()

    def test_harvest_missing_blackboard_silently_discarded(self) -> None:
        """Detach Blackboard while query pending, silently discarded."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: dispatch
        engine.world.detach(eid, Blackboard)
        engine.step()  # tick 2: harvest (blackboard gone, discard)

        assert not engine.world.has(eid, Blackboard)
        system.shutdown()


class TestCooldown:
    """Test cooldown state machine."""

    def test_cooldown_after_max_retries(self) -> None:
        """After max_retries consecutive errors, cooldown_until is set."""
        manager = _setup_basic()
        client = MockClient(responses={}, error_rate=1.0)
        manager.register_client(client)
        system = make_llm_system(manager)

        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=2,
                max_retries=3,
                cooldown_ticks=10,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Accumulate 3 errors using state-driven stepping.
        # Sleep between steps ensures the worker thread has time to
        # complete futures before the next harvest phase checks them.
        for _ in range(3):
            # Step until dispatched
            for _ in range(20):
                engine.step()
                if engine.world.get(eid, LLMAgent).pending:
                    break
            # Step until harvested (pending clears)
            for _ in range(20):
                time.sleep(0.002)
                engine.step()
                if not engine.world.get(eid, LLMAgent).pending:
                    break

        agent = engine.world.get(eid, LLMAgent)
        assert agent.consecutive_errors == 3
        assert agent.cooldown_until > 0

        system.shutdown()

    def test_cooldown_expires_and_entity_retries(self) -> None:
        """After cooldown expires, entity can query again."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        agent = LLMAgent(
            role="test_role",
            personality="test_personality",
            context="test_context",
            query_interval=1,
        )
        agent.cooldown_until = 5
        engine.world.attach(eid, agent)
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Ticks 1-4: cooldown (5 > tick_number)
        for _ in range(4):
            engine.step()
            agent = engine.world.get(eid, LLMAgent)
            assert agent.pending is False

        # Tick 5: cooldown expired (5 > 5 is False), eligible
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True

        system.shutdown()

    def test_success_resets_consecutive_errors(self) -> None:
        """Successful response resets consecutive_errors to 0."""
        manager = _setup_basic()
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        agent = LLMAgent(
            role="test_role",
            personality="test_personality",
            context="test_context",
            query_interval=2,
        )
        agent.consecutive_errors = 2
        engine.world.attach(eid, agent)
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch
        engine.step()  # tick 3: harvest success

        agent = engine.world.get(eid, LLMAgent)
        assert agent.consecutive_errors == 0

        system.shutdown()


class TestConfigErrors:
    """Test configuration error handling."""

    def test_missing_role_fires_on_error_missing_definition(self) -> None:
        """Missing role fires on_error with 'missing_definition'."""
        manager = _setup_basic()
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="missing_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Tick 1: config error fires
        engine.step()

        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert len(calls) == 1
        assert calls[0][1] == "missing_definition"

        system.shutdown()

    def test_missing_personality_fires_on_error(self) -> None:
        manager = _setup_basic()
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="missing_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert len(calls) == 1
        assert calls[0][1] == "missing_definition"

        system.shutdown()

    def test_missing_context_fires_on_error(self) -> None:
        manager = _setup_basic()
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="missing_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert len(calls) == 1
        assert calls[0][1] == "missing_definition"

        system.shutdown()

    def test_missing_parser_fires_on_error(self) -> None:
        manager = _setup_basic()
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                parser="missing_parser",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert len(calls) == 1
        assert calls[0][1] == "missing_definition"

        system.shutdown()

    def test_no_client_fires_on_error(self) -> None:
        manager = _setup_basic()
        manager._client = None
        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert len(calls) == 1
        assert calls[0][1] == "no_client"

        system.shutdown()


class TestCallbacks:
    """Test callback invocation."""

    def test_on_query_callback_fires(self) -> None:
        """on_query fires with eid, prompt_size, tick."""
        manager = _setup_basic()
        calls: list[tuple[int, int, int]] = []

        def on_query(eid: int, prompt_size: int, tick: int) -> None:
            calls.append((eid, prompt_size, tick))

        manager.on_query(on_query)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=2,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        engine.step()  # tick 1: skip
        engine.step()  # tick 2: dispatch

        assert len(calls) == 1
        assert calls[0][0] == eid
        assert isinstance(calls[0][1], int)
        assert calls[0][2] == 2

        system.shutdown()

    def test_callback_exception_does_not_crash_system(self) -> None:
        """Callback that raises is swallowed, system continues."""
        manager = _setup_basic()

        def bad_callback(eid: int, prompt_size: int, tick: int) -> None:
            raise RuntimeError("callback error")

        manager.on_query(bad_callback)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Should not crash
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True

        system.shutdown()


class TestTimeout:
    """Test query timeout handling."""

    def test_timeout_cancels_pending_query(self) -> None:
        """High latency + low timeout fires on_error."""
        config = LLMConfig(
            max_queries_per_tick=5,
            max_queries_per_second=50,
            query_timeout=0.01,
        )
        manager = LLMManager(config=config)
        manager.define_role("test_role", "You are a test agent.")
        manager.define_personality("test_personality", "You are helpful.")
        manager.define_context("test_context", lambda w, e: "Act.")
        client = MockClient(responses={}, latency=0.05)
        manager.register_client(client)

        calls: list[tuple[int, str, str, int]] = []

        def on_error(eid: int, etype: str, emsg: str, tick: int) -> None:
            calls.append((eid, etype, emsg, tick))

        manager.on_error(on_error)
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="test_role",
                personality="test_personality",
                context="test_context",
                query_interval=100,  # high interval prevents re-dispatch
            ),
        )
        engine.world.attach(eid, Blackboard())
        engine.add_system(system)

        # Manually set last_query_tick so entity is eligible on tick 1
        agent = engine.world.get(eid, LLMAgent)
        agent.last_query_tick = -100

        engine.step()  # tick 1: dispatch (latency=0.05s, won't complete soon)
        time.sleep(0.02)  # wait for timeout to elapse
        engine.step()  # tick 2: timeout fires (0.02s > 0.01s timeout)

        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is False
        assert any(c[1] == "timeout" for c in calls)

        system.shutdown()
