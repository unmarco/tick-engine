"""Integration tests for tick-llm full lifecycle."""
import time

from tick import Engine
from tick_ai.components import Blackboard
from tick_llm import (
    LLMAgent,
    LLMConfig,
    LLMManager,
    MockClient,
    make_llm_system,
)


class TestFullLifecycle:
    """Test complete LLM query lifecycle."""

    def test_full_lifecycle_dispatch_harvest_blackboard(self):
        """Test define defs, spawn entity, step engine, verify Blackboard."""
        # Setup manager with all definitions
        config = LLMConfig(max_queries_per_tick=5)
        manager = LLMManager(config=config)
        manager.define_role("scout", "You are a scout agent.")
        manager.define_personality("cautious", "You prefer stealth and observation.")
        manager.define_context(
            "scout_context", lambda world, eid: "Scan the area for threats."
        )

        # Custom parser that writes to a specific key
        def scout_parser(response, blackboard):
            blackboard.data["scout_report"] = response

        manager.define_parser("scout_parser", scout_parser)

        # Mock client returns JSON
        client = MockClient(
            responses=lambda sys, usr: '{"status": "all clear", "threat_level": 0}'
        )
        manager.register_client(client)

        # Create engine and system
        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        engine.add_system(system)

        # Spawn entity with query_interval=2 to cleanly separate dispatch/harvest
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="scout",
                personality="cautious",
                context="scout_context",
                parser="scout_parser",
                query_interval=2,
            ),
        )
        engine.world.attach(eid, Blackboard())

        # Tick 1: not eligible (1 - 0 = 1 < 2)
        engine.step()
        blackboard = engine.world.get(eid, Blackboard)
        assert "scout_report" not in blackboard.data

        # Tick 2: dispatch (2 - 0 = 2 >= 2)
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        assert agent.pending is True

        # Tick 3: harvest (3 - 2 = 1 < 2, no re-dispatch)
        engine.step()
        agent = engine.world.get(eid, LLMAgent)
        blackboard = engine.world.get(eid, Blackboard)
        assert agent.pending is False
        assert "scout_report" in blackboard.data
        assert "all clear" in blackboard.data["scout_report"]

        system.shutdown()

    def test_multiple_entities_with_different_roles(self):
        """Test two entities with different roles get correct responses."""
        config = LLMConfig(max_queries_per_tick=10)
        manager = LLMManager(config=config)

        # Define two roles
        manager.define_role("predator", "You are a predator.")
        manager.define_role("prey", "You are prey.")
        manager.define_personality("aggressive", "You attack.")
        manager.define_personality("defensive", "You flee.")
        manager.define_context("predator_ctx", lambda w, e: "Hunt.")
        manager.define_context("prey_ctx", lambda w, e: "Hide.")

        # Mock client returns different responses based on prompt
        def dynamic_response(sys_prompt, usr_msg):
            if "predator" in sys_prompt:
                return '{"action": "hunt"}'
            elif "prey" in sys_prompt:
                return '{"action": "flee"}'
            return "{}"

        client = MockClient(responses=dynamic_response)
        manager.register_client(client)

        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        engine.add_system(system)

        # Spawn predator
        pred_eid = engine.world.spawn()
        engine.world.attach(
            pred_eid,
            LLMAgent(
                role="predator",
                personality="aggressive",
                context="predator_ctx",
                query_interval=1,
            ),
        )
        engine.world.attach(pred_eid, Blackboard())

        # Spawn prey
        prey_eid = engine.world.spawn()
        engine.world.attach(
            prey_eid,
            LLMAgent(
                role="prey",
                personality="defensive",
                context="prey_ctx",
                query_interval=1,
            ),
        )
        engine.world.attach(prey_eid, Blackboard())

        # Tick 0-1: dispatch both
        engine.step()
        engine.step()

        # Tick 2: harvest both
        engine.step()

        pred_bb = engine.world.get(pred_eid, Blackboard)
        prey_bb = engine.world.get(prey_eid, Blackboard)

        assert "strategy" in pred_bb.data
        assert pred_bb.data["strategy"]["action"] == "hunt"

        assert "strategy" in prey_bb.data
        assert prey_bb.data["strategy"]["action"] == "flee"

        system.shutdown()

    def test_rate_limited_entities_stagger_across_ticks(self):
        """Test 3 entities, max_queries_per_tick=1, verify one per tick."""
        config = LLMConfig(max_queries_per_tick=1, max_queries_per_second=50)
        manager = LLMManager(config=config)

        manager.define_role("agent", "Agent.")
        manager.define_personality("neutral", "Neutral.")
        manager.define_context("ctx", lambda w, e: "Act.")

        client = MockClient(responses={})
        manager.register_client(client)

        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        engine.add_system(system)

        # Spawn 3 entities with high query_interval to prevent re-dispatch
        eids = []
        for _ in range(3):
            eid = engine.world.spawn()
            agent = LLMAgent(
                role="agent",
                personality="neutral",
                context="ctx",
                query_interval=100,
            )
            agent.last_query_tick = -100  # make eligible on tick 1
            engine.world.attach(eid, agent)
            engine.world.attach(eid, Blackboard())
            eids.append(eid)

        # Tick 1: all 3 eligible, max_per_tick=1 → 1 dispatched
        engine.step()
        dispatched_tick1 = sum(
            1 for eid in eids if engine.world.get(eid, LLMAgent).pending
        )
        assert dispatched_tick1 == 1

        # Tick 2: harvest first, dispatch second → 2 have been dispatched
        engine.step()
        dispatched_tick2 = sum(
            1
            for eid in eids
            if engine.world.get(eid, LLMAgent).last_query_tick > 0
        )
        assert dispatched_tick2 >= 2

        # Tick 3: harvest second, dispatch third → all 3 dispatched
        engine.step()
        dispatched_tick3 = sum(
            1
            for eid in eids
            if engine.world.get(eid, LLMAgent).last_query_tick > 0
        )
        assert dispatched_tick3 == 3

        system.shutdown()

    def test_error_recovery_after_cooldown(self):
        """Test entity hits errors, enters cooldown, eventually recovers."""
        config = LLMConfig(max_queries_per_tick=10)
        manager = LLMManager(config=config)

        manager.define_role("agent", "Agent.")
        manager.define_personality("neutral", "Neutral.")
        manager.define_context("ctx", lambda w, e: "Act.")

        # Client that fails first 3 times, then succeeds
        attempt = [0]

        class FlakeyClient:
            def query(self, sys_prompt, usr_msg):
                attempt[0] += 1
                if attempt[0] <= 3:
                    raise RuntimeError("transient error")
                return "{}"

        manager.register_client(FlakeyClient())

        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="agent",
                personality="neutral",
                context="ctx",
                query_interval=2,
                max_retries=3,
                cooldown_ticks=5,
            ),
        )
        engine.world.attach(eid, Blackboard())

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
        cooldown_until = agent.cooldown_until
        assert cooldown_until > engine.clock.tick_number

        # Step until entity is dispatched again (cooldown expires, attempt=4 succeeds)
        for _ in range(50):
            engine.step()
            if engine.world.get(eid, LLMAgent).pending:
                break

        # Step until harvest completes
        for _ in range(20):
            time.sleep(0.002)
            engine.step()
            if not engine.world.get(eid, LLMAgent).pending:
                break

        agent = engine.world.get(eid, LLMAgent)
        assert agent.consecutive_errors == 0  # Reset on success
        assert agent.pending is False

        system.shutdown()

    def test_system_with_custom_parser(self):
        """Test custom parser writes to a different Blackboard key."""
        config = LLMConfig(max_queries_per_tick=5)
        manager = LLMManager(config=config)

        manager.define_role("agent", "Agent.")
        manager.define_personality("neutral", "Neutral.")
        manager.define_context("ctx", lambda w, e: "Act.")

        # Custom parser writes to "custom_data" instead of "strategy"
        def custom_parser(response, blackboard):
            blackboard.data["custom_data"] = {"raw": response, "parsed": True}

        manager.define_parser("custom_parser", custom_parser)

        client = MockClient(responses=lambda s, u: "custom response")
        manager.register_client(client)

        system = make_llm_system(manager)
        engine = Engine(tps=20, seed=42)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            LLMAgent(
                role="agent",
                personality="neutral",
                context="ctx",
                parser="custom_parser",
                query_interval=1,
            ),
        )
        engine.world.attach(eid, Blackboard())

        # Dispatch and harvest
        engine.step()
        engine.step()
        engine.step()

        blackboard = engine.world.get(eid, Blackboard)
        assert "custom_data" in blackboard.data
        assert blackboard.data["custom_data"]["raw"] == "custom response"
        assert blackboard.data["custom_data"]["parsed"] is True
        assert "strategy" not in blackboard.data  # Default parser not used

        system.shutdown()
