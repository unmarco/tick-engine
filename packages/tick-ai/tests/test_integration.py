"""Integration tests for BT + Utility + Blackboard working together."""
import pytest

from tick import Engine
from tick_ai.components import BehaviorTree, Blackboard, UtilityAgent
from tick_ai.manager import AIManager
from tick_ai.nodes import Action, Condition, Selector, Sequence, Status
from tick_ai.systems import make_bt_system, make_utility_system


class TestFullIntegration:
    """Test all AI systems working together."""

    def test_bt_and_utility_same_entity(self):
        """An entity can have both BehaviorTree and UtilityAgent."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        # Setup BT
        manager.register_action("bt_act", lambda w, c, e: Status.SUCCESS)
        bt_nodes = {"root": Action(id="root", action="bt_act")}
        manager.define_tree("bt_tree", "root", bt_nodes)

        # Setup Utility
        manager.register_consideration("cons", lambda w, e: 0.7)
        manager.define_utility_action("util_act", ["cons"])
        manager.define_utility_selector("util_sel", ["util_act"])

        bt_system = make_bt_system(manager)
        util_system = make_utility_system(manager)
        engine.add_system(bt_system)
        engine.add_system(util_system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="bt_tree"))
        engine.world.attach(eid, UtilityAgent(selector_name="util_sel"))

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        agent = engine.world.get(eid, UtilityAgent)
        assert bt.status == "success"
        assert agent.selected_action == "util_act"

    def test_all_three_components(self):
        """Entity with BehaviorTree, UtilityAgent, and Blackboard."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def write_bb(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["written"] = True
            return Status.SUCCESS

        manager.register_action("write", write_bb)
        nodes = {"root": Action(id="root", action="write")}
        manager.define_tree("tree", "root", nodes)

        manager.register_consideration("c", lambda w, e: 0.5)
        manager.define_utility_action("act", ["c"])
        manager.define_utility_selector("sel", ["act"])

        bt_system = make_bt_system(manager)
        util_system = make_utility_system(manager)
        engine.add_system(bt_system)
        engine.add_system(util_system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="tree"))
        engine.world.attach(eid, UtilityAgent(selector_name="sel"))
        engine.world.attach(eid, Blackboard())

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        agent = engine.world.get(eid, UtilityAgent)
        bb = engine.world.get(eid, Blackboard)

        assert bt.status == "success"
        assert agent.selected_action == "act"
        assert bb.data["written"] is True

    def test_utility_consideration_reads_blackboard(self):
        """Utility consideration can read from blackboard."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def health_consideration(world, eid):
            bb = world.get(eid, Blackboard)
            hp = bb.data.get("hp", 100)
            return hp / 100.0  # Normalize to 0-1

        manager.register_consideration("health", health_consideration)
        manager.define_utility_action("heal", ["health"])
        manager.define_utility_selector("sel", ["heal"])

        system = make_utility_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="sel"))
        engine.world.attach(eid, Blackboard(data={"hp": 50}))

        engine.step()

        agent = engine.world.get(eid, UtilityAgent)
        assert agent.selected_action == "heal"
        assert agent.score == pytest.approx(0.5)

    def test_bt_action_uses_utility_result(self):
        """BT action can read utility agent's selected action."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def execute_selected(world, ctx, eid):
            agent = world.get(eid, UtilityAgent)
            bb = world.get(eid, Blackboard)
            bb.data["executed"] = agent.selected_action
            return Status.SUCCESS

        manager.register_action("execute", execute_selected)
        nodes = {"root": Action(id="root", action="execute")}
        manager.define_tree("tree", "root", nodes)

        manager.register_consideration("c", lambda w, e: 0.8)
        manager.define_utility_action("attack", ["c"])
        manager.define_utility_selector("sel", ["attack"])

        # Run utility system first, then BT
        util_system = make_utility_system(manager)
        bt_system = make_bt_system(manager)
        engine.add_system(util_system)
        engine.add_system(bt_system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="sel"))
        engine.world.attach(eid, BehaviorTree(tree_name="tree"))
        engine.world.attach(eid, Blackboard())

        engine.step()

        bb = engine.world.get(eid, Blackboard)
        assert bb.data["executed"] == "attack"

    def test_multi_tick_complex_scenario(self):
        """Complex multi-tick scenario with state changes."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def check_ready(world, eid):
            bb = world.get(eid, Blackboard)
            return bb.data.get("ready", False)

        def prepare(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["ready"] = True
            return Status.SUCCESS

        def execute(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["executed"] = True
            return Status.SUCCESS

        manager.register_condition("is_ready", check_ready)
        manager.register_action("prepare", prepare)
        manager.register_action("execute", execute)

        nodes = {
            "root": Selector(id="root", children=("ready_seq", "prep")),
            "ready_seq": Sequence(id="ready_seq", children=("check", "exec")),
            "check": Condition(id="check", condition="is_ready"),
            "exec": Action(id="exec", action="execute"),
            "prep": Action(id="prep", action="prepare"),
        }
        manager.define_tree("tree", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="tree"))
        engine.world.attach(eid, Blackboard())

        # Tick 1: Not ready, run prepare
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["ready"] is True
        assert "executed" not in bb.data

        # Tick 2: Now ready, run execute
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["executed"] is True

    def test_multiple_entities_different_configs(self):
        """Multiple entities with different AI configurations."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        manager.register_action("f", lambda w, c, e: Status.FAILURE)
        nodes1 = {"root": Action(id="root", action="s")}
        nodes2 = {"root": Action(id="root", action="f")}
        manager.define_tree("tree1", "root", nodes1)
        manager.define_tree("tree2", "root", nodes2)

        manager.register_consideration("c1", lambda w, e: 0.3)
        manager.register_consideration("c2", lambda w, e: 0.9)
        manager.define_utility_action("act1", ["c1"])
        manager.define_utility_action("act2", ["c2"])
        manager.define_utility_selector("sel1", ["act1"])
        manager.define_utility_selector("sel2", ["act2"])

        bt_system = make_bt_system(manager)
        util_system = make_utility_system(manager)
        engine.add_system(bt_system)
        engine.add_system(util_system)

        # Entity 1: tree1 + sel1 + bb1
        eid1 = engine.world.spawn()
        engine.world.attach(eid1, BehaviorTree(tree_name="tree1"))
        engine.world.attach(eid1, UtilityAgent(selector_name="sel1"))
        engine.world.attach(eid1, Blackboard(data={"id": 1}))

        # Entity 2: tree2 + sel2 + bb2
        eid2 = engine.world.spawn()
        engine.world.attach(eid2, BehaviorTree(tree_name="tree2"))
        engine.world.attach(eid2, UtilityAgent(selector_name="sel2"))
        engine.world.attach(eid2, Blackboard(data={"id": 2}))

        engine.step()

        bt1 = engine.world.get(eid1, BehaviorTree)
        bt2 = engine.world.get(eid2, BehaviorTree)
        agent1 = engine.world.get(eid1, UtilityAgent)
        agent2 = engine.world.get(eid2, UtilityAgent)
        bb1 = engine.world.get(eid1, Blackboard)
        bb2 = engine.world.get(eid2, Blackboard)

        assert bt1.status == "success"
        assert bt2.status == "failure"
        assert agent1.selected_action == "act1"
        assert agent2.selected_action == "act2"
        assert bb1.data["id"] == 1
        assert bb2.data["id"] == 2

    def test_bt_running_with_utility_updating(self):
        """BT can be running while utility continues to update."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        tick_count = [0]

        def run_three_ticks(world, ctx, eid):
            tick_count[0] += 1
            if tick_count[0] < 3:
                return Status.RUNNING
            return Status.SUCCESS

        manager.register_action("run", run_three_ticks)
        nodes = {"root": Action(id="root", action="run")}
        manager.define_tree("tree", "root", nodes)

        value = [0.5]

        def dynamic_cons(world, eid):
            return value[0]

        manager.register_consideration("dyn", dynamic_cons)
        manager.define_utility_action("act", ["dyn"])
        manager.define_utility_selector("sel", ["act"])

        bt_system = make_bt_system(manager)
        util_system = make_utility_system(manager)
        engine.add_system(bt_system)
        engine.add_system(util_system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="tree"))
        engine.world.attach(eid, UtilityAgent(selector_name="sel"))

        # Tick 1
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        agent = engine.world.get(eid, UtilityAgent)
        assert bt.status == "running"
        assert agent.score == pytest.approx(0.5)

        # Change utility score
        value[0] = 0.9

        # Tick 2
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        agent = engine.world.get(eid, UtilityAgent)
        assert bt.status == "running"
        assert agent.score == pytest.approx(0.9)

        # Tick 3
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        agent = engine.world.get(eid, UtilityAgent)
        assert bt.status == "success"
        assert agent.score == pytest.approx(0.9)

    def test_callback_integration(self):
        """Test on_status and on_select callbacks together."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("s", lambda w, c, e: Status.SUCCESS)
        nodes = {"root": Action(id="root", action="s")}
        manager.define_tree("tree", "root", nodes)

        manager.register_consideration("c", lambda w, e: 0.7)
        manager.define_utility_action("act", ["c"])
        manager.define_utility_selector("sel", ["act"])

        bt_calls = []
        util_calls = []

        def on_status(world, ctx, eid, status):
            bt_calls.append((eid, status))

        def on_select(world, ctx, eid, action, score):
            util_calls.append((eid, action, score))

        bt_system = make_bt_system(manager, on_status=on_status)
        util_system = make_utility_system(manager, on_select=on_select)
        engine.add_system(bt_system)
        engine.add_system(util_system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="tree"))
        engine.world.attach(eid, UtilityAgent(selector_name="sel"))

        engine.step()

        assert len(bt_calls) == 1
        assert bt_calls[0] == (eid, "success")
        assert len(util_calls) == 1
        assert util_calls[0] == (eid, "act", pytest.approx(0.7))

    def test_shared_blackboard_data(self):
        """BT and utility both read/write same blackboard data."""
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def bt_write(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["counter"] = bb.data.get("counter", 0) + 1
            return Status.SUCCESS

        manager.register_action("write", bt_write)
        nodes = {"root": Action(id="root", action="write")}
        manager.define_tree("tree", "root", nodes)

        def read_counter(world, eid):
            bb = world.get(eid, Blackboard)
            return bb.data.get("counter", 0) / 10.0

        manager.register_consideration("counter_cons", read_counter)
        manager.define_utility_action("act", ["counter_cons"])
        manager.define_utility_selector("sel", ["act"])

        # Utility runs first, reads counter (0), then BT writes counter (1)
        util_system = make_utility_system(manager)
        bt_system = make_bt_system(manager)
        engine.add_system(util_system)
        engine.add_system(bt_system)

        eid = engine.world.spawn()
        engine.world.attach(eid, UtilityAgent(selector_name="sel"))
        engine.world.attach(eid, BehaviorTree(tree_name="tree"))
        engine.world.attach(eid, Blackboard())

        # Tick 1
        engine.step()
        agent = engine.world.get(eid, UtilityAgent)
        bb = engine.world.get(eid, Blackboard)
        assert agent.score == pytest.approx(0.0)  # counter was 0
        assert bb.data["counter"] == 1  # BT incremented

        # Tick 2
        engine.step()
        agent = engine.world.get(eid, UtilityAgent)
        bb = engine.world.get(eid, Blackboard)
        assert agent.score == pytest.approx(0.1)  # counter was 1
        assert bb.data["counter"] == 2  # BT incremented

        # Tick 3
        engine.step()
        agent = engine.world.get(eid, UtilityAgent)
        bb = engine.world.get(eid, Blackboard)
        assert agent.score == pytest.approx(0.2)  # counter was 2
        assert bb.data["counter"] == 3
