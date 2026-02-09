"""Tests for tick_ability.types — AbilityDef and AbilityState dataclasses."""
from __future__ import annotations

from tick_ability.types import AbilityDef, AbilityState


class TestAbilityDef:
    def test_construction_with_defaults(self) -> None:
        ab = AbilityDef(name="test", duration=5)
        assert ab.name == "test"
        assert ab.duration == 5
        assert ab.cooldown == 0
        assert ab.max_charges == 1
        assert ab.charge_regen == 0
        assert ab.conditions == []

    def test_construction_with_random_duration(self) -> None:
        ab = AbilityDef(name="test", duration=(3, 7))
        assert ab.duration == (3, 7)
        assert isinstance(ab.duration, tuple)
        assert len(ab.duration) == 2

    def test_construction_with_all_fields(self) -> None:
        ab = AbilityDef(
            name="fireball",
            duration=10,
            cooldown=20,
            max_charges=3,
            charge_regen=5,
            conditions=["has_mana", "not_silenced"],
        )
        assert ab.name == "fireball"
        assert ab.duration == 10
        assert ab.cooldown == 20
        assert ab.max_charges == 3
        assert ab.charge_regen == 5
        assert ab.conditions == ["has_mana", "not_silenced"]

    def test_conditions_default_to_empty_list(self) -> None:
        ab1 = AbilityDef(name="test1", duration=5)
        ab2 = AbilityDef(name="test2", duration=5)
        # Ensure they have separate lists
        ab1.conditions.append("test")
        assert ab1.conditions == ["test"]
        assert ab2.conditions == []

    def test_unlimited_charges(self) -> None:
        ab = AbilityDef(name="test", duration=5, max_charges=-1)
        assert ab.max_charges == -1

    def test_no_regen(self) -> None:
        ab = AbilityDef(name="test", duration=5, charge_regen=0)
        assert ab.charge_regen == 0


class TestAbilityState:
    def test_construction_with_defaults(self) -> None:
        state = AbilityState(name="test", charges=2)
        assert state.name == "test"
        assert state.charges == 2
        assert state.cooldown_remaining == 0
        assert state.active_remaining == 0
        assert state.active_started_at == -1
        assert state.regen_remaining == 0

    def test_construction_with_all_fields(self) -> None:
        state = AbilityState(
            name="shield",
            charges=3,
            cooldown_remaining=5,
            active_remaining=10,
            active_started_at=42,
            regen_remaining=7,
        )
        assert state.name == "shield"
        assert state.charges == 3
        assert state.cooldown_remaining == 5
        assert state.active_remaining == 10
        assert state.active_started_at == 42
        assert state.regen_remaining == 7

    def test_mutability(self) -> None:
        state = AbilityState(name="test", charges=5)
        # Modify all fields
        state.charges = 3
        state.cooldown_remaining = 10
        state.active_remaining = 8
        state.active_started_at = 100
        state.regen_remaining = 2

        assert state.charges == 3
        assert state.cooldown_remaining == 10
        assert state.active_remaining == 8
        assert state.active_started_at == 100
        assert state.regen_remaining == 2

    def test_default_values_correctness(self) -> None:
        state = AbilityState(name="test", charges=0)
        # Check all defaults are zero except active_started_at (-1)
        assert state.cooldown_remaining == 0
        assert state.active_remaining == 0
        assert state.active_started_at == -1
        assert state.regen_remaining == 0
