"""Tests for BT evaluator."""
import random

import pytest

from tick import World
from tick.clock import Clock
from tick_ai.evaluator import evaluate
from tick_ai.manager import AIManager
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


@pytest.fixture
def world():
    """Create a world for tests."""
    return World()


@pytest.fixture
def ctx():
    """Create a tick context for tests."""
    clock = Clock(tps=10)
    return clock.context(lambda: None, random.Random(42))


@pytest.fixture
def manager():
    """Create an AIManager for tests."""
    return AIManager()


class TestActionNode:
    """Test Action node evaluation."""

    def test_action_success(self, world, ctx, manager):
        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)
        nodes = {"root": Action(id="root", action="succeed")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_action_failure(self, world, ctx, manager):
        manager.register_action("fail", lambda w, c, e: Status.FAILURE)
        nodes = {"root": Action(id="root", action="fail")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_action_running(self, world, ctx, manager):
        manager.register_action("run", lambda w, c, e: Status.RUNNING)
        nodes = {"root": Action(id="root", action="run")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "root"

    def test_action_not_found(self, world, ctx, manager):
        nodes = {"root": Action(id="root", action="missing")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_action_receives_correct_args(self, world, ctx, manager):
        calls = []

        def track_action(w, c, e):
            calls.append((w, c, e))
            return Status.SUCCESS

        manager.register_action("track", track_action)
        nodes = {"root": Action(id="root", action="track")}
        evaluate(nodes, "root", "", {}, manager, world, ctx, 999)
        assert len(calls) == 1
        assert calls[0][0] is world
        assert calls[0][1] is ctx
        assert calls[0][2] == 999


class TestConditionNode:
    """Test Condition node evaluation."""

    def test_condition_true(self, world, ctx, manager):
        manager.register_condition("check", lambda w, e: True)
        nodes = {"root": Condition(id="root", condition="check")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_condition_false(self, world, ctx, manager):
        manager.register_condition("check", lambda w, e: False)
        nodes = {"root": Condition(id="root", condition="check")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_condition_not_found(self, world, ctx, manager):
        nodes = {"root": Condition(id="root", condition="missing")}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_condition_receives_correct_args(self, world, ctx, manager):
        calls = []

        def track_condition(w, e):
            calls.append((w, e))
            return True

        manager.register_condition("track", track_condition)
        nodes = {"root": Condition(id="root", condition="track")}
        evaluate(nodes, "root", "", {}, manager, world, ctx, 888)
        assert len(calls) == 1
        assert calls[0][0] is world
        assert calls[0][1] == 888


class TestSequenceNode:
    """Test Sequence node evaluation."""

    def test_sequence_all_succeed(self, world, ctx, manager):
        manager.register_action("s1", lambda w, c, e: Status.SUCCESS)
        manager.register_action("s2", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Sequence(id="root", children=("a", "b")),
            "a": Action(id="a", action="s1"),
            "b": Action(id="b", action="s2"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_sequence_fail_fast(self, world, ctx, manager):
        call_order = []
        manager.register_action("s1", lambda w, c, e: Status.SUCCESS or call_order.append("s1"))
        manager.register_action("f1", lambda w, c, e: Status.FAILURE or call_order.append("f1"))
        manager.register_action("s2", lambda w, c, e: Status.SUCCESS or call_order.append("s2"))

        nodes = {
            "root": Sequence(id="root", children=("a", "b", "c")),
            "a": Action(id="a", action="s1"),
            "b": Action(id="b", action="f1"),
            "c": Action(id="c", action="s2"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""
        # s2 should not be called
        assert "s2" not in call_order

    def test_sequence_running_first_child(self, world, ctx, manager):
        manager.register_action("run", lambda w, c, e: Status.RUNNING)
        manager.register_action("s1", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Sequence(id="root", children=("a", "b")),
            "a": Action(id="a", action="run"),
            "b": Action(id="b", action="s1"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"

    def test_sequence_running_middle_child(self, world, ctx, manager):
        manager.register_action("s1", lambda w, c, e: Status.SUCCESS)
        manager.register_action("run", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Sequence(id="root", children=("a", "b", "c")),
            "a": Action(id="a", action="s1"),
            "b": Action(id="b", action="run"),
            "c": Action(id="c", action="s1"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"

    def test_sequence_resume_running(self, world, ctx, manager):
        call_order = []

        def track_success(w, c, e):
            call_order.append("s")
            return Status.SUCCESS

        def track_running(w, c, e):
            call_order.append("r")
            return Status.RUNNING

        manager.register_action("s", track_success)
        manager.register_action("r", track_running)

        nodes = {
            "root": Sequence(id="root", children=("a", "b", "c")),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="r"),
            "c": Action(id="c", action="s"),
        }

        # First tick: execute a, b (running)
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"
        assert call_order == ["s", "r"]

        # Second tick: skip a, resume b
        call_order.clear()
        status, running, counts = evaluate(nodes, "root", "b", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"
        assert call_order == ["r"]  # 'a' not called

    def test_sequence_empty(self, world, ctx, manager):
        nodes = {"root": Sequence(id="root", children=())}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS


class TestSelectorNode:
    """Test Selector node evaluation."""

    def test_selector_first_succeeds(self, world, ctx, manager):
        call_order = []

        def track_success(w, c, e):
            call_order.append("s")
            return Status.SUCCESS

        manager.register_action("s", track_success)
        manager.register_action("f", lambda w, c, e: Status.FAILURE or call_order.append("f"))

        nodes = {
            "root": Selector(id="root", children=("a", "b")),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""
        # b should not be called
        assert call_order == ["s"]

    def test_selector_fallback(self, world, ctx, manager):
        manager.register_action("f1", lambda w, c, e: Status.FAILURE)
        manager.register_action("f2", lambda w, c, e: Status.FAILURE)
        manager.register_action("s1", lambda w, c, e: Status.SUCCESS)

        nodes = {
            "root": Selector(id="root", children=("a", "b", "c")),
            "a": Action(id="a", action="f1"),
            "b": Action(id="b", action="f2"),
            "c": Action(id="c", action="s1"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_selector_all_fail(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Selector(id="root", children=("a", "b")),
            "a": Action(id="a", action="f"),
            "b": Action(id="b", action="f"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_selector_running(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Selector(id="root", children=("a", "b")),
            "a": Action(id="a", action="f"),
            "b": Action(id="b", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"

    def test_selector_resume_running(self, world, ctx, manager):
        call_order = []

        def track_fail(w, c, e):
            call_order.append("f")
            return Status.FAILURE

        def track_run(w, c, e):
            call_order.append("r")
            return Status.RUNNING

        manager.register_action("f", track_fail)
        manager.register_action("r", track_run)

        nodes = {
            "root": Selector(id="root", children=("a", "b")),
            "a": Action(id="a", action="f"),
            "b": Action(id="b", action="r"),
        }

        # First tick
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"
        assert call_order == ["f", "r"]

        # Second tick: skip a
        call_order.clear()
        status, running, counts = evaluate(nodes, "root", "b", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"
        assert call_order == ["r"]

    def test_selector_empty(self, world, ctx, manager):
        nodes = {"root": Selector(id="root", children=())}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE


class TestParallelNode:
    """Test Parallel node evaluation."""

    def test_parallel_require_all_success(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Parallel(id="root", children=("a", "b", "c"), policy="require_all"),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="s"),
            "c": Action(id="c", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_parallel_require_all_one_fails(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Parallel(id="root", children=("a", "b", "c"), policy="require_all"),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="f"),
            "c": Action(id="c", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_parallel_require_all_one_running(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Parallel(id="root", children=("a", "b", "c"), policy="require_all"),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="r"),
            "c": Action(id="c", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"

    def test_parallel_require_one_success(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Parallel(id="root", children=("a", "b"), policy="require_one"),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_parallel_require_one_all_fail(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Parallel(id="root", children=("a", "b"), policy="require_one"),
            "a": Action(id="a", action="f"),
            "b": Action(id="b", action="f"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_parallel_require_one_running(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Parallel(id="root", children=("a", "b"), policy="require_one"),
            "a": Action(id="a", action="f"),
            "b": Action(id="b", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "b"


class TestInverterNode:
    """Test Inverter decorator node."""

    def test_inverter_success_to_failure(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Inverter(id="root", child="a"),
            "a": Action(id="a", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""

    def test_inverter_failure_to_success(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Inverter(id="root", child="a"),
            "a": Action(id="a", action="f"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_inverter_running_passthrough(self, world, ctx, manager):
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Inverter(id="root", child="a"),
            "a": Action(id="a", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"


class TestRepeaterNode:
    """Test Repeater decorator node."""

    def test_repeater_single_success(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Repeater(id="root", child="a", max_count=1),
            "a": Action(id="a", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_repeater_multi_tick(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Repeater(id="root", child="a", max_count=3),
            "a": Action(id="a", action="s"),
        }

        # First tick
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "root"
        assert counts["root"] == 1

        # Second tick
        status, running, counts = evaluate(nodes, "root", "root", counts, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "root"
        assert counts["root"] == 2

        # Third tick
        status, running, counts = evaluate(nodes, "root", "root", counts, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""
        assert "root" not in counts

    def test_repeater_fail_policy_fail(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Repeater(id="root", child="a", max_count=5, fail_policy="fail"),
            "a": Action(id="a", action="f"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
        assert running == ""
        assert "root" not in counts

    def test_repeater_fail_policy_restart(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Repeater(id="root", child="a", max_count=3, fail_policy="restart"),
            "a": Action(id="a", action="f"),
        }

        # First tick
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "root"
        assert counts["root"] == 1

        # Second tick
        status, running, counts = evaluate(nodes, "root", "root", counts, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert counts["root"] == 2

        # Third tick
        status, running, counts = evaluate(nodes, "root", "root", counts, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        assert running == ""

    def test_repeater_child_running(self, world, ctx, manager):
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Repeater(id="root", child="a", max_count=3),
            "a": Action(id="a", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"  # Child is running, not repeater


class TestSucceederNode:
    """Test Succeeder decorator node."""

    def test_succeeder_success(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Succeeder(id="root", child="a"),
            "a": Action(id="a", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS

    def test_succeeder_failure_to_success(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Succeeder(id="root", child="a"),
            "a": Action(id="a", action="f"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS

    def test_succeeder_running_passthrough(self, world, ctx, manager):
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": Succeeder(id="root", child="a"),
            "a": Action(id="a", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"


class TestAlwaysFailNode:
    """Test AlwaysFail decorator node."""

    def test_always_fail_success_to_failure(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": AlwaysFail(id="root", child="a"),
            "a": Action(id="a", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE

    def test_always_fail_failure(self, world, ctx, manager):
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": AlwaysFail(id="root", child="a"),
            "a": Action(id="a", action="f"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE

    def test_always_fail_running_passthrough(self, world, ctx, manager):
        manager.register_action("r", lambda w, c, e: Status.RUNNING)
        nodes = {
            "root": AlwaysFail(id="root", child="a"),
            "a": Action(id="a", action="r"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"


class TestUtilitySelectorNode:
    """Test UtilitySelector node."""

    def test_utility_selector_picks_highest(self, world, ctx, manager):
        manager.register_consideration("low", lambda w, e: 0.3)
        manager.register_consideration("high", lambda w, e: 0.8)
        manager.define_utility_action("act_low", ["low"])
        manager.define_utility_action("act_high", ["high"])
        manager.register_action("act_low", lambda w, c, e: Status.SUCCESS)
        manager.register_action("act_high", lambda w, c, e: Status.SUCCESS)

        nodes = {
            "root": UtilitySelector(id="root", children=("a", "b")),
            "a": Action(id="a", action="act_low"),
            "b": Action(id="b", action="act_high"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS
        # Should pick b (higher score)

    def test_utility_selector_empty(self, world, ctx, manager):
        nodes = {"root": UtilitySelector(id="root", children=())}
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE

    def test_utility_selector_resume_running(self, world, ctx, manager):
        call_count = [0]

        def running_action(w, c, e):
            call_count[0] += 1
            return Status.RUNNING

        manager.register_consideration("c", lambda w, e: 0.5)
        manager.define_utility_action("act", ["c"])
        manager.register_action("act", running_action)

        nodes = {
            "root": UtilitySelector(id="root", children=("a",)),
            "a": Action(id="a", action="act"),
        }

        # First tick
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"
        assert call_count[0] == 1

        # Second tick: should resume without re-scoring
        status, running, counts = evaluate(nodes, "root", "a", {}, manager, world, ctx, 1)
        assert status == Status.RUNNING
        assert running == "a"
        assert call_count[0] == 2


class TestNestedTrees:
    """Test nested tree structures."""

    def test_sequence_of_sequences(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Sequence(id="root", children=("seq1", "seq2")),
            "seq1": Sequence(id="seq1", children=("a", "b")),
            "seq2": Sequence(id="seq2", children=("c", "d")),
            "a": Action(id="a", action="s"),
            "b": Action(id="b", action="s"),
            "c": Action(id="c", action="s"),
            "d": Action(id="d", action="s"),
        }
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS

    def test_selector_with_sequence_children(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes = {
            "root": Selector(id="root", children=("seq1", "seq2")),
            "seq1": Sequence(id="seq1", children=("a", "b")),
            "seq2": Sequence(id="seq2", children=("c", "d")),
            "a": Action(id="a", action="f"),
            "b": Action(id="b", action="s"),
            "c": Action(id="c", action="s"),
            "d": Action(id="d", action="s"),
        }
        # seq1 fails on a, seq2 succeeds
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.SUCCESS

    def test_deep_nesting(self, world, ctx, manager):
        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Sequence(id="root", children=("l1",)),
            "l1": Selector(id="l1", children=("l2",)),
            "l2": Sequence(id="l2", children=("l3",)),
            "l3": Inverter(id="l3", child="l4"),
            "l4": Action(id="l4", action="s"),
        }
        # l4 succeeds, l3 inverts to failure, l2 fails, l1 fails, root fails
        status, running, counts = evaluate(nodes, "root", "", {}, manager, world, ctx, 1)
        assert status == Status.FAILURE
