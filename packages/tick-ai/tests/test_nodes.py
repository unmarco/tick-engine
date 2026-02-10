"""Tests for BT node types and Status enum."""
from dataclasses import FrozenInstanceError

import pytest

from tick_ai.nodes import (
    Action,
    AlwaysFail,
    Condition,
    Inverter,
    Parallel,
    Repeater,
    Selector,
    Sequence,
    Status,
    Succeeder,
    UtilitySelector,
)


class TestStatus:
    """Test the Status enum."""

    def test_status_values(self):
        assert Status.SUCCESS.value == "success"
        assert Status.FAILURE.value == "failure"
        assert Status.RUNNING.value == "running"

    def test_status_enum_members(self):
        assert Status.SUCCESS == Status.SUCCESS
        assert Status.FAILURE != Status.SUCCESS
        assert Status.RUNNING != Status.FAILURE


class TestLeafNodes:
    """Test leaf node types."""

    def test_action_creation(self):
        node = Action(id="attack", action="do_attack")
        assert node.id == "attack"
        assert node.action == "do_attack"

    def test_action_frozen(self):
        node = Action(id="attack", action="do_attack")
        with pytest.raises(FrozenInstanceError):
            node.id = "other"  # type: ignore

    def test_condition_creation(self):
        node = Condition(id="check", condition="is_alive")
        assert node.id == "check"
        assert node.condition == "is_alive"

    def test_condition_frozen(self):
        node = Condition(id="check", condition="is_alive")
        with pytest.raises(FrozenInstanceError):
            node.condition = "other"  # type: ignore


class TestCompositeNodes:
    """Test composite node types."""

    def test_sequence_creation(self):
        node = Sequence(id="seq", children=("a", "b", "c"))
        assert node.id == "seq"
        assert node.children == ("a", "b", "c")

    def test_sequence_default_children(self):
        node = Sequence(id="seq")
        assert node.children == ()

    def test_sequence_frozen(self):
        node = Sequence(id="seq", children=("a", "b"))
        with pytest.raises(FrozenInstanceError):
            node.id = "other"  # type: ignore

    def test_selector_creation(self):
        node = Selector(id="sel", children=("a", "b", "c"))
        assert node.id == "sel"
        assert node.children == ("a", "b", "c")

    def test_selector_default_children(self):
        node = Selector(id="sel")
        assert node.children == ()

    def test_parallel_creation(self):
        node = Parallel(id="par", children=("a", "b"), policy="require_one")
        assert node.id == "par"
        assert node.children == ("a", "b")
        assert node.policy == "require_one"

    def test_parallel_default_policy(self):
        node = Parallel(id="par", children=("a",))
        assert node.policy == "require_all"

    def test_utility_selector_creation(self):
        node = UtilitySelector(id="util", children=("a", "b"))
        assert node.id == "util"
        assert node.children == ("a", "b")


class TestDecoratorNodes:
    """Test decorator node types."""

    def test_inverter_creation(self):
        node = Inverter(id="inv", child="target")
        assert node.id == "inv"
        assert node.child == "target"

    def test_inverter_default_child(self):
        node = Inverter(id="inv")
        assert node.child == ""

    def test_repeater_creation(self):
        node = Repeater(id="rep", child="act", max_count=5, fail_policy="restart")
        assert node.id == "rep"
        assert node.child == "act"
        assert node.max_count == 5
        assert node.fail_policy == "restart"

    def test_repeater_defaults(self):
        node = Repeater(id="rep")
        assert node.child == ""
        assert node.max_count == 1
        assert node.fail_policy == "fail"

    def test_succeeder_creation(self):
        node = Succeeder(id="succ", child="act")
        assert node.id == "succ"
        assert node.child == "act"

    def test_succeeder_default_child(self):
        node = Succeeder(id="succ")
        assert node.child == ""

    def test_always_fail_creation(self):
        node = AlwaysFail(id="fail", child="act")
        assert node.id == "fail"
        assert node.child == "act"

    def test_always_fail_default_child(self):
        node = AlwaysFail(id="fail")
        assert node.child == ""

    def test_all_decorators_frozen(self):
        inv = Inverter(id="inv", child="c")
        with pytest.raises(FrozenInstanceError):
            inv.child = "other"  # type: ignore

        rep = Repeater(id="rep", child="c")
        with pytest.raises(FrozenInstanceError):
            rep.max_count = 10  # type: ignore

        succ = Succeeder(id="succ", child="c")
        with pytest.raises(FrozenInstanceError):
            succ.id = "other"  # type: ignore

        fail = AlwaysFail(id="fail", child="c")
        with pytest.raises(FrozenInstanceError):
            fail.child = "other"  # type: ignore
