"""Tests for utility AI system."""
import pytest

from tick import Engine
from tick_ai.components import UtilityAgent
from tick_ai.manager import AIManager
from tick_ai.systems import make_utility_system


class TestUtilitySystem:
    """Test make_utility_system factory."""

    def test_system_selects_action(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("c1", lambda w, e: 0.5)
        manager.define_utility_action("act1", ["c1"])
        manager.define_utility_selector("selector", ["act1"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == "act1"
        assert agent.score == pytest.approx(0.5)

    def test_system_picks_highest_score(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("low", lambda w, e: 0.3)
        manager.register_consideration("high", lambda w, e: 0.8)
        manager.define_utility_action("act_low", ["low"])
        manager.define_utility_action("act_high", ["high"])
        manager.define_utility_selector("selector", ["act_low", "act_high"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == "act_high"
        assert agent.score == pytest.approx(0.8)

    def test_system_selector_not_found(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="missing"))

        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == ""
        assert agent.score == 0.0

    def test_on_select_callback(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("c1", lambda w, e: 0.7)
        manager.define_utility_action("act1", ["c1"])
        manager.define_utility_selector("selector", ["act1"])

        calls = []

        def on_select(world, ctx, eid, action_name, score):
            calls.append((eid, action_name, score))

        system = make_utility_system(manager, on_select=on_select)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        engine.step()

        assert len(calls) == 1
        assert calls[0][0] == eid
        assert calls[0][1] == "act1"
        assert calls[0][2] == pytest.approx(0.7)

    def test_on_select_not_called_for_empty(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.define_utility_selector("empty", [])

        calls = []

        def on_select(world, ctx, eid, action_name, score):
            calls.append((eid, action_name, score))

        system = make_utility_system(manager, on_select=on_select)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="empty"))

        engine.step()

        assert len(calls) == 0

    def test_multiple_entities(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("c1", lambda w, e: 0.5)
        manager.register_consideration("c2", lambda w, e: 0.9)
        manager.define_utility_action("act1", ["c1"])
        manager.define_utility_action("act2", ["c2"])
        manager.define_utility_selector("sel1", ["act1"])
        manager.define_utility_selector("sel2", ["act2"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid1 = engine.world.spawn()
        eid2 = engine.world.spawn()
        engine.world.attach(eid1, UtilityAgent(selector_name="sel1"))
        engine.world.attach(eid2, UtilityAgent(selector_name="sel2"))

        engine.step()

        agent1 = engine.world.get(eid1, UtilityAgent)
        agent2 = engine.world.get(eid2, UtilityAgent)
        assert agent1.selected_action == "act1"
        assert agent1.score == pytest.approx(0.5)
        assert agent2.selected_action == "act2"
        assert agent2.score == pytest.approx(0.9)

    def test_system_without_callback(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("c1", lambda w, e: 0.5)
        manager.define_utility_action("act1", ["c1"])
        manager.define_utility_selector("selector", ["act1"])

        system = make_utility_system(manager, on_select=None)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        # Should not crash
        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == "act1"

    def test_multiplicative_scoring(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("c1", lambda w, e: 0.8)
        manager.register_consideration("c2", lambda w, e: 0.5)
        manager.register_consideration("c3", lambda w, e: 0.5)
        manager.define_utility_action("act1", ["c1", "c2", "c3"])
        manager.define_utility_selector("selector", ["act1"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == "act1"
        assert agent.score == pytest.approx(0.2)  # 0.8 * 0.5 * 0.5

    def test_zero_score_selected(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_consideration("zero", lambda w, e: 0.0)
        manager.define_utility_action("act1", ["zero"])
        manager.define_utility_selector("selector", ["act1"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == "act1"
        assert agent.score == 0.0

    def test_system_updates_every_tick(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        value = [0.5]

        def dynamic_consideration(w, e):
            return value[0]

        manager.register_consideration("dynamic", dynamic_consideration)
        manager.define_utility_action("act1", ["dynamic"])
        manager.define_utility_selector("selector", ["act1"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="selector"))

        # Tick 1
        engine.step()
        agent = engine.world.get(eid, UtilityAgent)
        assert agent.score == pytest.approx(0.5)

        # Change value
        value[0] = 0.9

        # Tick 2
        engine.step()
        agent = engine.world.get(eid, UtilityAgent)
        assert agent.score == pytest.approx(0.9)
