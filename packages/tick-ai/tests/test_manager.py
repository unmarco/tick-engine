"""Tests for AIManager."""
import pytest

from tick import World
from tick_ai.manager import AIManager
from tick_ai.nodes import Action, Condition, Selector, Sequence, Status


class TestTreeDefinition:
    """Test tree definition and lookup."""

    def test_define_simple_tree(self):
        manager = AIManager()
        nodes = {
            "root": Action(id="root", action="attack"),
        }
        manager.define_tree("simple", "root", nodes)
        result = manager.tree("simple")
        assert result is not None
        root_id, node_dict = result
        assert root_id == "root"
        assert node_dict == nodes

    def test_define_tree_with_sequence(self):
        manager = AIManager()
        nodes = {
            "root": Sequence(id="root", children=("a", "b")),
            "a": Action(id="a", action="move"),
            "b": Action(id="b", action="attack"),
        }
        manager.define_tree("seq_tree", "root", nodes)
        result = manager.tree("seq_tree")
        assert result is not None
        root_id, node_dict = result
        assert root_id == "root"
        assert len(node_dict) == 3

    def test_tree_not_found(self):
        manager = AIManager()
        assert manager.tree("nonexistent") is None

    def test_multiple_trees(self):
        manager = AIManager()
        nodes1 = {"root": Action(id="root", action="a1")}
        nodes2 = {"root": Action(id="root", action="a2")}
        manager.define_tree("tree1", "root", nodes1)
        manager.define_tree("tree2", "root", nodes2)

        t1 = manager.tree("tree1")
        t2 = manager.tree("tree2")
        assert t1 is not None
        assert t2 is not None
        assert t1[1]["root"].action == "a1"  # type: ignore
        assert t2[1]["root"].action == "a2"  # type: ignore


class TestTreeValidation:
    """Test tree validation errors."""

    def test_root_not_in_nodes(self):
        manager = AIManager()
        nodes = {
            "action": Action(id="action", action="test"),
        }
        with pytest.raises(ValueError, match="Root node 'missing' not found"):
            manager.define_tree("bad", "missing", nodes)

    def test_node_id_mismatch(self):
        manager = AIManager()
        nodes = {
            "wrong_key": Action(id="correct_id", action="test"),
        }
        with pytest.raises(ValueError, match="Node key 'wrong_key' does not match"):
            manager.define_tree("bad", "wrong_key", nodes)

    def test_missing_child_reference(self):
        manager = AIManager()
        nodes = {
            "root": Sequence(id="root", children=("a", "missing")),
            "a": Action(id="a", action="test"),
        }
        with pytest.raises(ValueError, match="references unknown child 'missing'"):
            manager.define_tree("bad", "root", nodes)

    def test_valid_tree_does_not_raise(self):
        manager = AIManager()
        nodes = {
            "root": Selector(id="root", children=("a", "b")),
            "a": Condition(id="a", condition="check"),
            "b": Action(id="b", action="fallback"),
        }
        manager.define_tree("valid", "root", nodes)  # Should not raise
        assert manager.tree("valid") is not None


class TestActionRegistration:
    """Test action callback registration."""

    def test_register_action(self):
        manager = AIManager()

        def my_action(world, ctx, eid):
            return Status.SUCCESS

        manager.register_action("test", my_action)
        result = manager.action("test")
        assert result is my_action

    def test_action_not_found(self):
        manager = AIManager()
        assert manager.action("nonexistent") is None

    def test_multiple_actions(self):
        manager = AIManager()

        def action1(world, ctx, eid):
            return Status.SUCCESS

        def action2(world, ctx, eid):
            return Status.FAILURE

        manager.register_action("a1", action1)
        manager.register_action("a2", action2)

        assert manager.action("a1") is action1
        assert manager.action("a2") is action2


class TestConditionRegistration:
    """Test condition callback registration."""

    def test_register_condition(self):
        manager = AIManager()

        def my_condition(world, eid):
            return True

        manager.register_condition("test", my_condition)
        result = manager.condition("test")
        assert result is my_condition

    def test_condition_not_found(self):
        manager = AIManager()
        assert manager.condition("nonexistent") is None

    def test_multiple_conditions(self):
        manager = AIManager()

        def cond1(world, eid):
            return True

        def cond2(world, eid):
            return False

        manager.register_condition("c1", cond1)
        manager.register_condition("c2", cond2)

        assert manager.condition("c1") is cond1
        assert manager.condition("c2") is cond2


class TestConsiderationRegistration:
    """Test consideration callback registration."""

    def test_register_consideration(self):
        manager = AIManager()

        def my_consideration(world, eid):
            return 0.5

        manager.register_consideration("test", my_consideration)
        result = manager.consideration("test")
        assert result is my_consideration

    def test_consideration_not_found(self):
        manager = AIManager()
        assert manager.consideration("nonexistent") is None

    def test_multiple_considerations(self):
        manager = AIManager()

        def cons1(world, eid):
            return 0.8

        def cons2(world, eid):
            return 0.3

        manager.register_consideration("cons1", cons1)
        manager.register_consideration("cons2", cons2)

        assert manager.consideration("cons1") is cons1
        assert manager.consideration("cons2") is cons2


class TestUtilityActionDefinition:
    """Test utility action definition."""

    def test_define_utility_action(self):
        manager = AIManager()
        manager.define_utility_action("attack", ["health", "distance"])
        # Can't directly inspect but we can score it later

    def test_define_utility_action_empty_considerations(self):
        manager = AIManager()
        manager.define_utility_action("idle", [])


class TestUtilitySelectorDefinition:
    """Test utility selector definition."""

    def test_define_utility_selector(self):
        manager = AIManager()
        manager.define_utility_selector("combat", ["attack", "defend"])
        result = manager.utility_selector("combat")
        assert result == ["attack", "defend"]

    def test_utility_selector_not_found(self):
        manager = AIManager()
        assert manager.utility_selector("nonexistent") is None

    def test_define_utility_selector_empty_actions(self):
        manager = AIManager()
        manager.define_utility_selector("empty", [])
        result = manager.utility_selector("empty")
        assert result == []


class TestScoreAction:
    """Test utility action scoring."""

    def test_score_action_simple(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("health", lambda w, e: 0.8)
        manager.register_consideration("distance", lambda w, e: 0.5)
        manager.define_utility_action("attack", ["health", "distance"])

        score = manager.score_action("attack", world, 1)
        assert score == pytest.approx(0.4)  # 0.8 * 0.5

    def test_score_action_multiplicative(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("c1", lambda w, e: 0.5)
        manager.register_consideration("c2", lambda w, e: 0.5)
        manager.register_consideration("c3", lambda w, e: 0.5)
        manager.define_utility_action("act", ["c1", "c2", "c3"])

        score = manager.score_action("act", world, 1)
        assert score == pytest.approx(0.125)  # 0.5 * 0.5 * 0.5

    def test_score_action_not_defined(self):
        manager = AIManager()
        world = World()
        score = manager.score_action("undefined", world, 1)
        assert score == 0.0

    def test_score_action_empty_considerations(self):
        manager = AIManager()
        world = World()
        manager.define_utility_action("act", [])
        score = manager.score_action("act", world, 1)
        assert score == 0.0

    def test_score_action_missing_consideration(self):
        manager = AIManager()
        world = World()
        manager.define_utility_action("act", ["missing_cons"])
        score = manager.score_action("act", world, 1)
        assert score == 0.0

    def test_score_action_zero_short_circuits(self):
        manager = AIManager()
        world = World()

        call_count = 0

        def cons1(w, e):
            return 0.0

        def cons2(w, e):
            nonlocal call_count
            call_count += 1
            return 0.5

        manager.register_consideration("zero", cons1)
        manager.register_consideration("after", cons2)
        manager.define_utility_action("act", ["zero", "after"])

        score = manager.score_action("act", world, 1)
        assert score == 0.0
        # cons2 should not be called due to short-circuit
        assert call_count == 0

    def test_score_action_clamping(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("over", lambda w, e: 1.5)
        manager.register_consideration("under", lambda w, e: -0.5)
        manager.define_utility_action("act", ["over", "under"])

        score = manager.score_action("act", world, 1)
        assert score == 0.0  # 1.0 * 0.0 (clamped)


class TestSelectAction:
    """Test utility selector action selection."""

    def test_select_action_highest_score(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("c1", lambda w, e: 0.5)
        manager.register_consideration("c2", lambda w, e: 0.8)
        manager.define_utility_action("low", ["c1"])
        manager.define_utility_action("high", ["c2"])
        manager.define_utility_selector("selector", ["low", "high"])

        name, score = manager.select_action("selector", world, 1)
        assert name == "high"
        assert score == pytest.approx(0.8)

    def test_select_action_first_on_tie(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("c", lambda w, e: 0.5)
        manager.define_utility_action("a1", ["c"])
        manager.define_utility_action("a2", ["c"])
        manager.define_utility_selector("selector", ["a1", "a2"])

        name, score = manager.select_action("selector", world, 1)
        assert name == "a1"  # First in list wins tie
        assert score == pytest.approx(0.5)

    def test_select_action_selector_not_found(self):
        manager = AIManager()
        world = World()

        name, score = manager.select_action("missing", world, 1)
        assert name == ""
        assert score == 0.0

    def test_select_action_empty_selector(self):
        manager = AIManager()
        world = World()

        manager.define_utility_selector("empty", [])

        name, score = manager.select_action("empty", world, 1)
        assert name == ""
        assert score == 0.0

    def test_select_action_all_zero_scores(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("zero", lambda w, e: 0.0)
        manager.define_utility_action("a1", ["zero"])
        manager.define_utility_action("a2", ["zero"])
        manager.define_utility_selector("selector", ["a1", "a2"])

        name, score = manager.select_action("selector", world, 1)
        assert name == "a1"  # First action even with zero score
        assert score == 0.0

    def test_select_action_complex_scenario(self):
        manager = AIManager()
        world = World()

        manager.register_consideration("health", lambda w, e: 0.9)
        manager.register_consideration("ammo", lambda w, e: 0.7)
        manager.register_consideration("distance", lambda w, e: 0.6)
        manager.define_utility_action("attack", ["health", "ammo"])
        manager.define_utility_action("defend", ["health"])
        manager.define_utility_action("flee", ["distance"])
        manager.define_utility_selector("combat", ["attack", "defend", "flee"])

        name, score = manager.select_action("combat", world, 1)
        # attack: 0.9 * 0.7 = 0.63
        # defend: 0.9
        # flee: 0.6
        assert name == "defend"
        assert score == pytest.approx(0.9)
