"""Integration tests for tick-colony LLM integration layer.

Tests end-to-end wiring between context builders, directive parser,
pressure system, and the LLM/AI components. Does NOT exercise the
actual LLM system execution (no threads).
"""

import json

from tick import Engine
from tick_colony import (
    register_colony_components,
    Grid2D,
    Pos2D,
    EventLog,
    ColonySnapshot,
    NeedSet,
    NeedHelper,
    Inventory,
    InventoryHelper,
    FSM,
    Blackboard,
    LLMAgent,
    make_resource_context,
    make_population_context,
    make_colony_context,
    make_directive_parser,
    PressureThresholds,
    make_pressure_system,
)
from tick_atlas import CellDef, CellMap


class TestRegisterColonyComponents:
    def test_register_includes_llmagent_and_blackboard(self) -> None:
        """register_colony_components registers LLMAgent and Blackboard."""
        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        eid = engine.world.spawn()
        engine.world.attach(
            eid, LLMAgent(role="strategist", personality="cautious", context="colony")
        )
        engine.world.attach(eid, Blackboard(data={"key": "value"}))

        assert engine.world.has(eid, LLMAgent)
        assert engine.world.has(eid, Blackboard)

        agent = engine.world.get(eid, LLMAgent)
        assert agent.role == "strategist"
        assert agent.personality == "cautious"
        assert agent.context == "colony"

        bb = engine.world.get(eid, Blackboard)
        assert bb.data["key"] == "value"


class TestColonyContext:
    def test_colony_context_combines_multiple_sections(self) -> None:
        """make_colony_context output contains Resources, Population,
        Spatial, and Recent Events sections."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(20, 20)
        event_log = EventLog()

        # Entity with Inventory
        e_stock = world.spawn()
        inv = Inventory(capacity=100)
        InventoryHelper.add(inv, "wood", 30)
        InventoryHelper.add(inv, "food", 15)
        world.attach(e_stock, inv)

        # Entity with NeedSet and FSM (population)
        e_pop = world.spawn()
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", value=80.0, max_val=100.0,
                       decay_rate=1.0, critical_threshold=20.0)
        world.attach(e_pop, ns)
        world.attach(e_pop, FSM(state="idle", transitions={}))
        world.attach(e_pop, Pos2D(x=5.0, y=5.0))
        grid.place(e_pop, (5, 5))

        # Emit an event
        event_log.emit(tick=1, type="harvest", amount=10)

        # LLM entity that will call the context function
        e_llm = world.spawn()
        world.attach(e_llm, Pos2D(x=10.0, y=10.0))
        grid.place(e_llm, (10, 10))

        ctx_fn = make_colony_context(
            grid=grid, event_log=event_log, include_strategy=False
        )
        output = ctx_fn(world, e_llm)

        assert "=== Resources ===" in output
        assert "=== Population ===" in output
        assert "=== Spatial ===" in output
        assert "=== Recent Events ===" in output
        assert "wood=30" in output
        assert "food=15" in output
        assert "harvest" in output

    def test_colony_context_includes_strategy_from_blackboard(self) -> None:
        """include_strategy=True appends Current Strategy from Blackboard."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        world.attach(eid, Blackboard(data={
            "strategy": {"stance": "defensive", "priority": "food"}
        }))

        ctx_fn = make_colony_context(include_strategy=True)
        output = ctx_fn(world, eid)

        assert "=== Current Strategy ===" in output
        assert "defensive" in output

    def test_colony_context_no_strategy_when_disabled(self) -> None:
        """include_strategy=False omits strategy even if Blackboard present."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        world.attach(eid, Blackboard(data={"strategy": {"stance": "offensive"}}))

        ctx_fn = make_colony_context(include_strategy=False)
        output = ctx_fn(world, eid)

        assert "Current Strategy" not in output


class TestDirectiveParser:
    def test_parser_dispatches_to_handlers_and_updates_blackboard(self) -> None:
        """Directive parser calls typed handlers and merges into strategy."""
        dispatched: list[tuple] = []

        def handle_assign(entry: dict) -> None:
            dispatched.append(("assign", entry))

        def handle_priority(entry: dict) -> None:
            dispatched.append(("priority", entry))

        parser = make_directive_parser(
            handlers={"assign_task": handle_assign, "set_priority": handle_priority}
        )

        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [
                {"type": "assign_task", "entity": 5, "task": "gather_wood"},
                {"type": "set_priority", "resource": "food", "level": "high"},
            ],
            "reasoning": "Food supplies are low",
            "confidence": 0.85,
        })

        parser(response, bb)

        assert len(dispatched) == 2
        assert dispatched[0][0] == "assign"
        assert dispatched[0][1]["entity"] == 5
        assert dispatched[1][0] == "priority"
        assert dispatched[1][1]["resource"] == "food"

        # Strategy written to blackboard
        strategy = bb.data["strategy"]
        assert "directives" in strategy
        assert strategy["reasoning"] == "Food supplies are low"
        assert strategy["confidence"] == 0.85

    def test_parser_uses_fallback_for_unknown_types(self) -> None:
        """Unknown directive types routed to fallback handler."""
        unknown: list[dict] = []

        parser = make_directive_parser(
            handlers={},
            fallback=lambda entry: unknown.append(entry),
        )

        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [
                {"type": "unknown_cmd", "detail": "something"},
            ]
        })

        parser(response, bb)

        assert len(unknown) == 1
        assert unknown[0]["type"] == "unknown_cmd"

    def test_parser_write_strategy_false_skips_merge(self) -> None:
        """write_strategy=False does not merge into blackboard."""
        parser = make_directive_parser(handlers={}, write_strategy=False)

        bb = Blackboard(data={})
        response = json.dumps({"directives": [], "reasoning": "test"})

        parser(response, bb)

        assert "strategy" not in bb.data


class TestPressureSystem:
    def test_pressure_triggers_on_resource_drop(self) -> None:
        """Significant resource change resets LLM agent cooldowns."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Stockpile entity
        e_stock = world.spawn()
        inv = Inventory(capacity=200)
        InventoryHelper.add(inv, "food", 100)
        world.attach(e_stock, inv)

        # LLM agent entity with a future cooldown
        e_llm = world.spawn()
        agent = LLMAgent(
            role="r", personality="p", context="c",
            cooldown_until=999, last_query_tick=50,
        )
        world.attach(e_llm, agent)

        pressure_events: list[tuple] = []

        def on_pressure(w, tick, ptype, mag):
            pressure_events.append((tick, ptype, mag))

        system = make_pressure_system(
            thresholds=PressureThresholds(resource_change=0.2),
            check_interval=1,
            on_pressure=on_pressure,
        )
        engine.add_system(system)

        # Tick 1: initializes baselines (prev_resources empty -> no trigger)
        engine.step()
        assert agent.cooldown_until == 999  # unchanged on init

        # Drop food from 100 to 50 (50% change >= 20% threshold)
        InventoryHelper.remove(inv, "food", 50)

        # Tick 2: detects change and resets
        engine.step()

        assert agent.cooldown_until == 0
        assert agent.last_query_tick == 0
        assert len(pressure_events) == 1
        assert pressure_events[0][1] == "resource_change"


class TestFullFlow:
    def test_context_to_parse_to_blackboard(self) -> None:
        """Build context, feed to parser, verify blackboard updated."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Resources
        e_stock = world.spawn()
        inv = Inventory(capacity=100)
        InventoryHelper.add(inv, "wood", 20)
        world.attach(e_stock, inv)

        # Population entity
        e_pop = world.spawn()
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", value=90.0, max_val=100.0,
                       decay_rate=1.0, critical_threshold=20.0)
        world.attach(e_pop, ns)

        # LLM entity with blackboard
        e_llm = world.spawn()
        bb = Blackboard(data={})
        world.attach(e_llm, bb)

        # Build context
        ctx_fn = make_colony_context(include_strategy=False)
        context_text = ctx_fn(world, e_llm)
        assert "wood=20" in context_text

        # Simulate LLM response
        llm_response = json.dumps({
            "directives": [
                {"type": "build", "structure": "wall", "count": 3},
            ],
            "stance": "defensive",
            "reasoning": "Need protection",
        })

        build_cmds: list[dict] = []
        parser = make_directive_parser(
            handlers={"build": lambda entry: build_cmds.append(entry)},
        )
        parser(llm_response, bb)

        # Handler was called
        assert len(build_cmds) == 1
        assert build_cmds[0]["structure"] == "wall"

        # Strategy merged into blackboard
        assert bb.data["strategy"]["stance"] == "defensive"
        assert bb.data["strategy"]["reasoning"] == "Need protection"


class TestSnapshotRestore:
    def test_snapshot_restore_preserves_llmagent(self) -> None:
        """LLMAgent fields survive snapshot/restore, pending reset to False."""
        engine1 = Engine(tps=20, seed=42)
        register_colony_components(engine1.world)

        eid = engine1.world.spawn()
        agent = LLMAgent(
            role="strategist", personality="cautious", context="colony",
            parser="directive", query_interval=50, priority=2,
            last_query_tick=10, pending=True, consecutive_errors=1,
            max_retries=5, cooldown_ticks=100, cooldown_until=200,
        )
        engine1.world.attach(eid, agent)

        snapper1 = ColonySnapshot()
        data = snapper1.snapshot(engine1)

        # Restore
        engine2 = Engine(tps=20, seed=42)
        snapper2 = ColonySnapshot()
        snapper2.restore(engine2, data)

        agent2 = engine2.world.get(eid, LLMAgent)
        assert agent2.role == "strategist"
        assert agent2.personality == "cautious"
        assert agent2.context == "colony"
        assert agent2.parser == "directive"
        assert agent2.query_interval == 50
        assert agent2.priority == 2
        assert agent2.last_query_tick == 10
        assert agent2.consecutive_errors == 1
        assert agent2.max_retries == 5
        assert agent2.cooldown_ticks == 100
        assert agent2.cooldown_until == 200
        # pending reset by ColonySnapshot.restore()
        assert agent2.pending is False

    def test_snapshot_restore_preserves_blackboard(self) -> None:
        """Blackboard data survives snapshot/restore."""
        engine1 = Engine(tps=20, seed=42)
        register_colony_components(engine1.world)

        eid = engine1.world.spawn()
        bb = Blackboard(data={
            "strategy": {"stance": "aggressive", "priority": "expansion"},
            "history": [1, 2, 3],
        })
        engine1.world.attach(eid, bb)

        snapper1 = ColonySnapshot()
        data = snapper1.snapshot(engine1)

        # Restore
        engine2 = Engine(tps=20, seed=42)
        snapper2 = ColonySnapshot()
        snapper2.restore(engine2, data)

        bb2 = engine2.world.get(eid, Blackboard)
        assert bb2.data["strategy"]["stance"] == "aggressive"
        assert bb2.data["strategy"]["priority"] == "expansion"
        assert bb2.data["history"] == [1, 2, 3]


class TestReExports:
    def test_all_llm_reexports_accessible(self) -> None:
        """All tick-llm and tick-ai re-exports importable from tick_colony."""
        from tick_colony import (
            AIManager,
            BehaviorTree,
            LLMManager,
            LLMSystem,
            MockClient,
            make_llm_system,
        )

        assert AIManager is not None
        assert BehaviorTree is not None
        assert LLMManager is not None
        assert LLMSystem is not None
        assert MockClient is not None
        assert callable(make_llm_system)

    def test_colony_context_reexports_accessible(self) -> None:
        """Colony LLM integration re-exports importable from tick_colony."""
        from tick_colony import (
            make_resource_context,
            make_population_context,
            make_colony_context,
            make_directive_parser,
            PressureThresholds,
            make_pressure_system,
        )

        assert callable(make_resource_context)
        assert callable(make_population_context)
        assert callable(make_colony_context)
        assert callable(make_directive_parser)
        assert PressureThresholds is not None
        assert callable(make_pressure_system)


class TestPressureAndContextTogether:
    def test_critical_needs_trigger_pressure_and_context_reports(self) -> None:
        """Entities with critical needs trigger pressure, and context
        builder correctly reports the critical state."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create population entities with needs
        entities = []
        for i in range(5):
            eid = world.spawn()
            ns = NeedSet(data={})
            # Start 3 out of 5 at critical levels
            if i < 3:
                value = 15.0  # below critical threshold of 20
            else:
                value = 80.0
            NeedHelper.add(ns, "hunger", value=value, max_val=100.0,
                           decay_rate=0.0, critical_threshold=20.0)
            world.attach(eid, ns)
            entities.append(eid)

        # Stockpile (so resource check doesn't interfere)
        e_stock = world.spawn()
        inv = Inventory(capacity=200)
        InventoryHelper.add(inv, "food", 100)
        world.attach(e_stock, inv)

        # LLM agent
        e_llm = world.spawn()
        agent = LLMAgent(
            role="r", personality="p", context="c",
            cooldown_until=500, last_query_tick=10,
        )
        world.attach(e_llm, agent)

        pressure_log: list[tuple] = []

        system = make_pressure_system(
            thresholds=PressureThresholds(
                critical_needs_ratio=0.5,
                resource_change=1.0,    # disable resource trigger
                population_change=1.0,  # disable population trigger
            ),
            check_interval=1,
            on_pressure=lambda w, t, p, m: pressure_log.append((t, p, m)),
        )
        engine.add_system(system)

        # Tick 1: resource/population baselines init (return False),
        # then critical fires immediately (3/5 = 60% >= 50%)
        engine.step()

        assert len(pressure_log) >= 1
        assert pressure_log[0][1] == "critical_needs"
        assert pressure_log[0][2] >= 0.5  # ratio

        assert agent.cooldown_until == 0
        assert agent.last_query_tick == 0

        # Verify context builder also reports the critical state
        pop_ctx = make_population_context(include_needs=True)
        pop_output = pop_ctx(world, e_llm)

        assert "Critical:" in pop_output
        assert "hunger" in pop_output
