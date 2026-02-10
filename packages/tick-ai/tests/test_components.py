"""Tests for AI components."""
from tick_ai.components import BehaviorTree, Blackboard, UtilityAgent


class TestBehaviorTree:
    """Test BehaviorTree component."""

    def test_creation_minimal(self):
        bt = BehaviorTree(tree_name="patrol")
        assert bt.tree_name == "patrol"
        assert bt.running_node == ""
        assert bt.status == ""
        assert bt.repeat_counts == {}

    def test_creation_full(self):
        bt = BehaviorTree(
            tree_name="combat",
            running_node="attack",
            status="running",
            repeat_counts={"rep1": 3, "rep2": 1},
        )
        assert bt.tree_name == "combat"
        assert bt.running_node == "attack"
        assert bt.status == "running"
        assert bt.repeat_counts == {"rep1": 3, "rep2": 1}

    def test_mutable(self):
        bt = BehaviorTree(tree_name="patrol")
        bt.running_node = "move"
        bt.status = "success"
        bt.repeat_counts = {"rep": 5}
        assert bt.running_node == "move"
        assert bt.status == "success"
        assert bt.repeat_counts == {"rep": 5}

    def test_repeat_counts_mutable_dict(self):
        bt = BehaviorTree(tree_name="patrol")
        bt.repeat_counts["rep1"] = 2
        bt.repeat_counts["rep2"] = 4
        assert bt.repeat_counts == {"rep1": 2, "rep2": 4}

    def test_repeat_counts_default_factory(self):
        bt1 = BehaviorTree(tree_name="tree1")
        bt2 = BehaviorTree(tree_name="tree2")
        bt1.repeat_counts["rep"] = 1
        assert "rep" not in bt2.repeat_counts


class TestBlackboard:
    """Test Blackboard component."""

    def test_creation_empty(self):
        bb = Blackboard()
        assert bb.data == {}

    def test_creation_with_data(self):
        bb = Blackboard(data={"hp": 100, "target": "enemy1"})
        assert bb.data == {"hp": 100, "target": "enemy1"}

    def test_mutable(self):
        bb = Blackboard()
        bb.data["hp"] = 50
        bb.data["mana"] = 75
        assert bb.data == {"hp": 50, "mana": 75}

    def test_data_default_factory(self):
        bb1 = Blackboard()
        bb2 = Blackboard()
        bb1.data["key"] = "value1"
        assert "key" not in bb2.data

    def test_various_value_types(self):
        bb = Blackboard()
        bb.data["int"] = 42
        bb.data["float"] = 3.14
        bb.data["str"] = "hello"
        bb.data["list"] = [1, 2, 3]
        bb.data["dict"] = {"nested": "data"}
        bb.data["none"] = None
        bb.data["bool"] = True

        assert bb.data["int"] == 42
        assert bb.data["float"] == 3.14
        assert bb.data["str"] == "hello"
        assert bb.data["list"] == [1, 2, 3]
        assert bb.data["dict"] == {"nested": "data"}
        assert bb.data["none"] is None
        assert bb.data["bool"] is True


class TestUtilityAgent:
    """Test UtilityAgent component."""

    def test_creation_minimal(self):
        agent = UtilityAgent(selector_name="combat_selector")
        assert agent.selector_name == "combat_selector"
        assert agent.selected_action == ""
        assert agent.score == 0.0

    def test_creation_full(self):
        agent = UtilityAgent(
            selector_name="combat_selector",
            selected_action="attack",
            score=0.85,
        )
        assert agent.selector_name == "combat_selector"
        assert agent.selected_action == "attack"
        assert agent.score == 0.85

    def test_mutable(self):
        agent = UtilityAgent(selector_name="selector")
        agent.selected_action = "defend"
        agent.score = 0.65
        assert agent.selected_action == "defend"
        assert agent.score == 0.65

    def test_score_float_precision(self):
        agent = UtilityAgent(selector_name="selector", score=0.123456789)
        assert agent.score == 0.123456789
