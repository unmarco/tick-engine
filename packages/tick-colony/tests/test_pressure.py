"""Tests for tick_colony.pressure — pressure monitor system for LLM re-query."""

from tick import Engine
from tick_colony.events import EventLog
from tick_colony.needs import NeedHelper, NeedSet
from tick_colony.pressure import PressureThresholds, make_pressure_system
from tick_llm.components import LLMAgent
from tick_resource import Inventory


def _make_agent(priority: int = 0) -> LLMAgent:
    """Create an LLMAgent with cooldown/last_query_tick set to non-zero."""
    return LLMAgent(
        role="r",
        personality="p",
        context="c",
        priority=priority,
        cooldown_until=100,
        last_query_tick=50,
    )


def _advance(engine: Engine, ticks: int) -> None:
    """Step the engine forward *ticks* times."""
    for _ in range(ticks):
        engine.step()


class TestCheckInterval:
    def test_no_check_before_interval(self):
        """System does nothing until check_interval ticks elapse."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Set up entity with agent and inventory so resource check could fire
        eid = world.spawn()
        world.attach(eid, Inventory(slots={"food": 100}))
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=5,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        # Advance 4 ticks — not enough for first check
        _advance(engine, 4)
        assert fired == []

    def test_check_fires_at_interval(self):
        """System performs check once check_interval ticks elapse."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Entity with critical needs to trigger pressure
        eid = world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0, decay_rate=0.0, critical_threshold=20.0)
        world.attach(eid, ns)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=5,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        # Advance 5 ticks — first check happens, critical needs should fire
        _advance(engine, 5)
        assert "critical_needs" in fired


class TestFirstCheckInitializesBaseline:
    def test_resource_first_check_does_not_fire(self):
        """First resource check initializes prev_resources, does not fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        world.attach(eid, Inventory(slots={"food": 100}))
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # First check — baseline init, no fire
        assert fired == []

    def test_population_first_check_does_not_fire(self):
        """First population check initializes prev_population, does not fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        for _ in range(10):
            eid = world.spawn()
            world.attach(eid, NeedSet())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()
        assert fired == []


class TestNoPressure:
    def test_no_fire_when_nothing_changed(self):
        """No pressure fires when colony state is static."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        world.attach(eid, Inventory(slots={"food": 100}))
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=80.0, max_val=100.0, decay_rate=0.0, critical_threshold=20.0)
        world.attach(eid, ns)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # First check — baseline
        engine.step()  # Second check — nothing changed
        engine.step()  # Third check
        assert fired == []


class TestResourcePressure:
    def test_resource_change_above_threshold_fires(self):
        """20%+ resource change triggers resource_change pressure."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        inv = Inventory(slots={"food": 100})
        world.attach(eid, inv)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append((pt, m)),
        )
        engine.add_system(system)

        engine.step()  # Baseline: food=100

        # Change resources by 25% (100 -> 75)
        inv.slots["food"] = 75

        engine.step()  # Should detect 25% drop
        assert len(fired) == 1
        assert fired[0][0] == "resource_change"
        assert fired[0][1] >= 0.2  # magnitude is the fractional change

    def test_resource_change_below_threshold_no_fire(self):
        """Less than 20% resource change does not trigger."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        inv = Inventory(slots={"food": 100})
        world.attach(eid, inv)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline: food=100

        # Change resources by only 10% (100 -> 90)
        inv.slots["food"] = 90

        engine.step()
        assert "resource_change" not in fired

    def test_resource_increase_also_fires(self):
        """Absolute change matters — increase also triggers."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        inv = Inventory(slots={"food": 100})
        world.attach(eid, inv)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline: food=100

        # Increase by 30%
        inv.slots["food"] = 130

        engine.step()
        assert "resource_change" in fired


class TestPopulationPressure:
    def test_population_increase_fires(self):
        """Adding entities with NeedSet triggers population_change."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Start with 10 entities
        eids = []
        for _ in range(10):
            eid = world.spawn()
            world.attach(eid, NeedSet())
            eids.append(eid)

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append((pt, m)),
        )
        engine.add_system(system)

        engine.step()  # Baseline: pop=10

        # Add 3 more entities — 30% increase (>= 15% threshold)
        for _ in range(3):
            eid = world.spawn()
            world.attach(eid, NeedSet())

        engine.step()
        assert len(fired) == 1
        assert fired[0][0] == "population_change"
        assert fired[0][1] >= 0.15

    def test_population_decrease_fires(self):
        """Removing NeedSet entities triggers population_change."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eids = []
        for _ in range(10):
            eid = world.spawn()
            world.attach(eid, NeedSet())
            eids.append(eid)

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline: pop=10

        # Remove 2 entities — 20% decrease (>= 15%)
        for eid in eids[:2]:
            world.despawn(eid)

        engine.step()
        assert "population_change" in fired

    def test_population_small_change_no_fire(self):
        """Population change below threshold does not fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eids = []
        for _ in range(20):
            eid = world.spawn()
            world.attach(eid, NeedSet())
            eids.append(eid)

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline: pop=20

        # Add 1 entity — 5% increase (< 15%)
        eid = world.spawn()
        world.attach(eid, NeedSet())

        engine.step()
        assert "population_change" not in fired


class TestCriticalNeedsPressure:
    def test_critical_ratio_above_threshold_fires(self):
        """When >= 30% of NeedSet entities have a critical need, fires."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # 10 entities, 4 with critical needs = 40% (>= 30%)
        for i in range(10):
            eid = world.spawn()
            ns = NeedSet()
            if i < 4:
                # Critical: value <= threshold
                NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                               decay_rate=0.0, critical_threshold=20.0)
            else:
                # Healthy
                NeedHelper.add(ns, "hunger", value=80.0, max_val=100.0,
                               decay_rate=0.0, critical_threshold=20.0)
            world.attach(eid, ns)

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append((pt, m)),
        )
        engine.add_system(system)

        # Critical needs fires on first check (no baseline needed for this check;
        # resource/population baseline init returns False, then critical runs)
        engine.step()
        assert any(pt == "critical_needs" for pt, _ in fired)
        # Magnitude should be 0.4 (4/10)
        crit_entry = next((pt, m) for pt, m in fired if pt == "critical_needs")
        assert abs(crit_entry[1] - 0.4) < 1e-9

    def test_critical_ratio_below_threshold_no_fire(self):
        """When < 30% of entities have critical needs, does not fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # 10 entities, 2 critical = 20% (< 30%)
        for i in range(10):
            eid = world.spawn()
            ns = NeedSet()
            if i < 2:
                NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                               decay_rate=0.0, critical_threshold=20.0)
            else:
                NeedHelper.add(ns, "hunger", value=80.0, max_val=100.0,
                               decay_rate=0.0, critical_threshold=20.0)
            world.attach(eid, ns)

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline
        engine.step()  # Second check
        assert "critical_needs" not in fired

    def test_no_needset_entities_no_fire(self):
        """Zero NeedSet entities means ratio is 0, no fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Only an agent, no NeedSet entities
        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()
        engine.step()
        assert fired == []


class TestEventBurstPressure:
    def test_event_burst_fires(self):
        """N events of tracked types within interval triggers event_burst."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        event_log = EventLog()
        thresholds = PressureThresholds(
            event_types=("attack", "disaster"),
            event_burst=5,
        )

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            event_log=event_log,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append((pt, m)),
        )
        engine.add_system(system)

        engine.step()  # Baseline check (tick 1)

        # Emit 5 events of tracked types after tick 1
        for i in range(3):
            event_log.emit(tick=2, type="attack", damage=10)
        for i in range(2):
            event_log.emit(tick=2, type="disaster", severity="high")

        engine.step()  # Check at tick 2 — should detect burst
        assert any(pt == "event_burst" for pt, _ in fired)
        burst_entry = next((pt, m) for pt, m in fired if pt == "event_burst")
        assert burst_entry[1] >= 5.0

    def test_event_burst_below_threshold_no_fire(self):
        """Fewer events than burst threshold does not fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        event_log = EventLog()
        thresholds = PressureThresholds(
            event_types=("attack",),
            event_burst=5,
        )

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            event_log=event_log,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline

        # Only 3 events (< 5 burst threshold)
        for i in range(3):
            event_log.emit(tick=2, type="attack", damage=5)

        engine.step()
        assert "event_burst" not in fired

    def test_untracked_event_types_ignored(self):
        """Events of types not in event_types are not counted."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        event_log = EventLog()
        thresholds = PressureThresholds(
            event_types=("attack",),
            event_burst=3,
        )

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            event_log=event_log,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline

        # 5 events, but of an untracked type
        for i in range(5):
            event_log.emit(tick=2, type="trade", amount=10)

        engine.step()
        assert "event_burst" not in fired

    def test_no_event_log_no_fire(self):
        """If no event_log provided, event burst never fires."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        thresholds = PressureThresholds(
            event_types=("attack",),
            event_burst=1,
        )

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            event_log=None,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()
        engine.step()
        assert "event_burst" not in fired


class TestCustomPressure:
    def test_custom_function_fires_at_1_0(self):
        """Custom pressure function returning >= 1.0 fires."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        thresholds = PressureThresholds(
            custom={"morale_crisis": lambda w: 1.5},
        )

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append((pt, m)),
        )
        engine.add_system(system)

        engine.step()  # Baseline for resources/pop (those don't fire first check)
        # Custom fires on first check since it has no baseline requirement
        assert any(pt == "morale_crisis" for pt, _ in fired)
        custom_entry = next((pt, m) for pt, m in fired if pt == "morale_crisis")
        assert custom_entry[1] == 1.5

    def test_custom_function_below_1_0_no_fire(self):
        """Custom function returning < 1.0 does not fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        agent_eid = world.spawn()
        world.attach(agent_eid, _make_agent())

        thresholds = PressureThresholds(
            custom={"morale_check": lambda w: 0.5},
        )

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()
        engine.step()
        assert "morale_check" not in fired


class TestAgentReset:
    def test_cooldown_and_last_query_tick_reset_to_zero(self):
        """On pressure fire, LLMAgent cooldown_until and last_query_tick reset."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                       decay_rate=0.0, critical_threshold=20.0)
        world.attach(eid, ns)

        agent = _make_agent()
        world.attach(eid, agent)

        assert agent.cooldown_until == 100
        assert agent.last_query_tick == 50

        system = make_pressure_system(check_interval=1)
        engine.add_system(system)

        # Critical needs fires on first check (1/1 entities critical);
        # resource/population baseline returns False, critical fires immediately
        engine.step()
        assert agent.cooldown_until == 0
        assert agent.last_query_tick == 0

    def test_min_priority_filter(self):
        """Only agents with priority >= min_priority are reset."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Entity to trigger critical needs
        trigger_eid = world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                       decay_rate=0.0, critical_threshold=20.0)
        world.attach(trigger_eid, ns)

        # Low priority agent (should NOT be reset)
        low_eid = world.spawn()
        low_agent = _make_agent(priority=1)
        world.attach(low_eid, low_agent)

        # High priority agent (should be reset)
        high_eid = world.spawn()
        high_agent = _make_agent(priority=5)
        world.attach(high_eid, high_agent)

        system = make_pressure_system(check_interval=1, min_priority=3)
        engine.add_system(system)

        # Critical fires on first check (1/1 NeedSet entities critical)
        engine.step()

        # Low-priority agent NOT reset
        assert low_agent.cooldown_until == 100
        assert low_agent.last_query_tick == 50

        # High-priority agent IS reset
        assert high_agent.cooldown_until == 0
        assert high_agent.last_query_tick == 0

    def test_multiple_agents_all_eligible_reset(self):
        """All agents meeting min_priority are reset, not just first."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        trigger_eid = world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                       decay_rate=0.0, critical_threshold=20.0)
        world.attach(trigger_eid, ns)

        agents = []
        for i in range(3):
            eid = world.spawn()
            agent = _make_agent(priority=i)
            world.attach(eid, agent)
            agents.append(agent)

        # min_priority=0 means all agents qualify
        system = make_pressure_system(check_interval=1, min_priority=0)
        engine.add_system(system)

        # Critical fires on first check (1/1 NeedSet entities critical)
        engine.step()

        for agent in agents:
            assert agent.cooldown_until == 0
            assert agent.last_query_tick == 0


class TestOnPressureCallback:
    def test_callback_receives_correct_args(self):
        """on_pressure callback receives (world, tick, pressure_type, magnitude)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                       decay_rate=0.0, critical_threshold=20.0)
        world.attach(eid, ns)
        world.attach(eid, _make_agent())

        calls = []

        def on_pressure(w, tick, ptype, magnitude):
            calls.append({
                "world": w,
                "tick": tick,
                "ptype": ptype,
                "magnitude": magnitude,
            })

        system = make_pressure_system(
            check_interval=1,
            on_pressure=on_pressure,
        )
        engine.add_system(system)

        # Critical fires on first check (tick 1): resource/pop baseline False,
        # then critical detects 1/1 entities critical
        engine.step()

        assert len(calls) == 1
        assert calls[0]["world"] is world
        assert calls[0]["tick"] == 1
        assert calls[0]["ptype"] == "critical_needs"
        assert isinstance(calls[0]["magnitude"], float)
        assert calls[0]["magnitude"] == 1.0  # 1/1 entities critical

    def test_no_callback_no_error(self):
        """System works without on_pressure callback (default None)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=5.0, max_val=100.0,
                       decay_rate=0.0, critical_threshold=20.0)
        world.attach(eid, ns)
        world.attach(eid, _make_agent())

        system = make_pressure_system(check_interval=1)
        engine.add_system(system)

        # Should not raise
        engine.step()
        engine.step()


class TestPriorityOrder:
    def test_first_pressure_type_wins_no_stacking(self):
        """Only the first detected pressure type fires; no stacking."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Set up both resource AND population to change
        eid = world.spawn()
        inv = Inventory(slots={"food": 100})
        world.attach(eid, inv)
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", value=80.0, max_val=100.0,
                       decay_rate=0.0, critical_threshold=20.0)
        world.attach(eid, ns)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline: food=100, pop=1

        # Change resources by 50% AND add population
        inv.slots["food"] = 50
        for _ in range(5):
            new_eid = world.spawn()
            world.attach(new_eid, NeedSet())

        engine.step()
        # Only resource_change should fire (checked first)
        assert fired == ["resource_change"]


class TestDefaultThresholds:
    def test_default_thresholds_used_when_none(self):
        """Default PressureThresholds used when thresholds=None."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        inv = Inventory(slots={"food": 100})
        world.attach(eid, inv)
        world.attach(eid, _make_agent())

        fired = []
        system = make_pressure_system(
            thresholds=None,  # Explicitly None
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append((pt, m)),
        )
        engine.add_system(system)

        engine.step()  # Baseline

        # Exactly 20% change (default threshold is 0.2, check is >=)
        inv.slots["food"] = 80

        engine.step()
        assert len(fired) == 1
        assert fired[0][0] == "resource_change"

    def test_custom_thresholds_override_default(self):
        """Custom thresholds are respected over defaults."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        eid = world.spawn()
        inv = Inventory(slots={"food": 100})
        world.attach(eid, inv)
        world.attach(eid, _make_agent())

        # Set very high resource threshold — 20% change should NOT fire
        thresholds = PressureThresholds(resource_change=0.5)

        fired = []
        system = make_pressure_system(
            thresholds=thresholds,
            check_interval=1,
            on_pressure=lambda w, t, pt, m: fired.append(pt),
        )
        engine.add_system(system)

        engine.step()  # Baseline

        inv.slots["food"] = 75  # 25% change, below 50% threshold

        engine.step()
        assert "resource_change" not in fired
