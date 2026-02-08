"""Tests for tick_colony.stats module - attribute + modifier system."""

import pytest
from tick_colony import StatBlock, Modifiers, effective, add_modifier, remove_modifiers, make_modifier_tick_system
from tick import Engine


class TestStatBlock:
    def test_statblock_creation(self):
        stats = StatBlock(data={"strength": 10.0, "agility": 15.0})
        assert stats.data["strength"] == 10.0
        assert stats.data["agility"] == 15.0

    def test_statblock_empty(self):
        stats = StatBlock(data={})
        assert stats.data == {}


class TestModifiers:
    def test_modifiers_creation(self):
        mods = Modifiers(entries=[
            ["strength", 5.0, 10],
            ["agility", -2.0, -1],
        ])
        assert len(mods.entries) == 2
        assert mods.entries[0] == ["strength", 5.0, 10]
        assert mods.entries[1] == ["agility", -2.0, -1]

    def test_modifiers_empty(self):
        mods = Modifiers(entries=[])
        assert mods.entries == []


class TestEffective:
    def test_effective_base_value_only(self):
        stats = StatBlock(data={"strength": 10.0})
        mods = Modifiers(entries=[])
        result = effective(stats, mods, "strength")
        assert result == 10.0

    def test_effective_with_positive_modifiers(self):
        stats = StatBlock(data={"strength": 10.0})
        mods = Modifiers(entries=[
            ["strength", 5.0, 10],
            ["strength", 3.0, 5],
        ])
        result = effective(stats, mods, "strength")
        assert result == 18.0  # 10 + 5 + 3

    def test_effective_with_negative_modifiers(self):
        stats = StatBlock(data={"agility": 20.0})
        mods = Modifiers(entries=[
            ["agility", -5.0, 3],
        ])
        result = effective(stats, mods, "agility")
        assert result == 15.0  # 20 - 5

    def test_effective_with_mixed_modifiers(self):
        stats = StatBlock(data={"defense": 50.0})
        mods = Modifiers(entries=[
            ["defense", 10.0, 5],
            ["defense", -3.0, 2],
            ["defense", 7.0, -1],
        ])
        result = effective(stats, mods, "defense")
        assert result == 64.0  # 50 + 10 - 3 + 7

    def test_effective_ignores_other_stats(self):
        stats = StatBlock(data={"strength": 10.0, "agility": 15.0})
        mods = Modifiers(entries=[
            ["strength", 5.0, 10],
            ["agility", 3.0, 5],
        ])
        result = effective(stats, mods, "strength")
        assert result == 15.0  # Only strength modifier applied

    def test_effective_stat_not_in_statblock(self):
        stats = StatBlock(data={"strength": 10.0})
        mods = Modifiers(entries=[])
        assert effective(stats, mods, "nonexistent") == 0.0


class TestAddModifier:
    def test_add_modifier_temporary(self):
        mods = Modifiers(entries=[])
        add_modifier(mods, "strength", 5.0, duration=10)
        assert len(mods.entries) == 1
        assert mods.entries[0] == ["strength", 5.0, 10]

    def test_add_modifier_permanent(self):
        mods = Modifiers(entries=[])
        add_modifier(mods, "agility", 3.0, duration=-1)
        assert len(mods.entries) == 1
        assert mods.entries[0] == ["agility", 3.0, -1]

    def test_add_modifier_default_permanent(self):
        mods = Modifiers(entries=[])
        add_modifier(mods, "defense", 10.0)
        assert mods.entries[0][2] == -1  # Default is permanent

    def test_add_multiple_modifiers(self):
        mods = Modifiers(entries=[])
        add_modifier(mods, "strength", 5.0, duration=10)
        add_modifier(mods, "strength", 3.0, duration=5)
        add_modifier(mods, "agility", 2.0, duration=-1)
        assert len(mods.entries) == 3


class TestRemoveModifiers:
    def test_remove_modifiers_for_stat(self):
        mods = Modifiers(entries=[
            ["strength", 5.0, 10],
            ["agility", 3.0, 5],
            ["strength", 2.0, -1],
        ])
        remove_modifiers(mods, "strength")
        assert len(mods.entries) == 1
        assert mods.entries[0][0] == "agility"

    def test_remove_modifiers_none_present(self):
        mods = Modifiers(entries=[
            ["agility", 3.0, 5],
        ])
        remove_modifiers(mods, "strength")
        assert len(mods.entries) == 1
        assert mods.entries[0][0] == "agility"

    def test_remove_modifiers_empty_list(self):
        mods = Modifiers(entries=[])
        remove_modifiers(mods, "strength")
        assert len(mods.entries) == 0


class TestModifierTickSystem:
    def test_modifier_tick_decrements_duration(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        mods = Modifiers(entries=[
            ["strength", 5.0, 5],
        ])
        world.attach(e1, mods)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        engine.step()
        assert mods.entries[0][2] == 4

        engine.step()
        assert mods.entries[0][2] == 3

    def test_modifier_tick_removes_expired(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        mods = Modifiers(entries=[
            ["strength", 5.0, 2],
            ["agility", 3.0, 5],
        ])
        world.attach(e1, mods)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        engine.step()  # strength: 1, agility: 4
        assert len(mods.entries) == 2

        engine.step()  # strength: 0 (removed), agility: 3
        assert len(mods.entries) == 1
        assert mods.entries[0][0] == "agility"
        assert mods.entries[0][2] == 3

    def test_permanent_modifiers_never_expire(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        mods = Modifiers(entries=[
            ["strength", 10.0, -1],
        ])
        world.attach(e1, mods)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        for _ in range(100):
            engine.step()

        assert len(mods.entries) == 1
        assert mods.entries[0][2] == -1  # Still -1

    def test_mixed_temporary_and_permanent(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        mods = Modifiers(entries=[
            ["strength", 5.0, 2],
            ["agility", 3.0, -1],
            ["defense", 7.0, 1],
        ])
        world.attach(e1, mods)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        engine.step()  # strength: 1, agility: -1, defense: 0 (removed)
        assert len(mods.entries) == 2

        engine.step()  # strength: 0 (removed), agility: -1
        assert len(mods.entries) == 1
        assert mods.entries[0][0] == "agility"
        assert mods.entries[0][2] == -1

    def test_multiple_entities_with_modifiers(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        e2 = world.spawn()

        mods1 = Modifiers(entries=[["strength", 5.0, 3]])
        mods2 = Modifiers(entries=[["agility", 2.0, 2]])

        world.attach(e1, mods1)
        world.attach(e2, mods2)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        engine.step()
        assert mods1.entries[0][2] == 2
        assert mods2.entries[0][2] == 1

        engine.step()
        assert mods1.entries[0][2] == 1
        assert len(mods2.entries) == 0  # Expired

    def test_all_modifiers_expire_simultaneously(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        mods = Modifiers(entries=[
            ["strength", 5.0, 1],
            ["agility", 3.0, 1],
            ["defense", 7.0, 1],
        ])
        world.attach(e1, mods)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        engine.step()
        assert len(mods.entries) == 0


class TestIntegration:
    def test_effective_with_decaying_modifiers(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        stats = StatBlock(data={"strength": 10.0})
        mods = Modifiers(entries=[
            ["strength", 5.0, 2],
            ["strength", 3.0, -1],
        ])
        world.attach(e1, stats)
        world.attach(e1, mods)

        modifier_system = make_modifier_tick_system()
        engine.add_system(modifier_system)

        # Initial effective: 10 + 5 + 3 = 18
        assert effective(stats, mods, "strength") == 18.0

        engine.step()
        # After 1 tick: 10 + 5 + 3 = 18 (first modifier has 1 tick left)
        assert effective(stats, mods, "strength") == 18.0

        engine.step()
        # After 2 ticks: 10 + 3 = 13 (first modifier expired, second is permanent)
        assert effective(stats, mods, "strength") == 13.0
