"""Tests for Blackboard integration with actions and conditions."""
import pytest

from tick import Engine
from tick_ai.components import BehaviorTree, Blackboard
from tick_ai.manager import AIManager
from tick_ai.nodes import Action, Condition, Sequence, Status
from tick_ai.systems import make_bt_system


class TestBlackboardIntegration:
    """Test Blackboard usage in BT actions and conditions."""

    def test_action_reads_blackboard(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def read_action(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            if bb.data.get("ready"):
                return Status.SUCCESS
            return Status.FAILURE

        manager.register_action("read", read_action)
        nodes = {"root": Action(id="root", action="read")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard(data={"ready": True}))

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"

    def test_action_writes_blackboard(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def write_action(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["written"] = True
            bb.data["tick"] = ctx.tick_number
            return Status.SUCCESS

        manager.register_action("write", write_action)
        nodes = {"root": Action(id="root", action="write")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard())

        engine.step()

        bb = engine.world.get(eid, Blackboard)
        assert bb.data["written"] is True
        assert bb.data["tick"] == 1

    def test_condition_reads_blackboard(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def check_condition(world, eid):
            bb = world.get(eid, Blackboard)
            return bb.data.get("enabled", False)

        manager.register_condition("check", check_condition)
        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)

        nodes = {
            "root": Sequence(id="root", children=("cond", "act")),
            "cond": Condition(id="cond", condition="check"),
            "act": Action(id="act", action="succeed"),
        }
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard(data={"enabled": True}))

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"

    def test_blackboard_persistence_across_ticks(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def increment_action(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            count = bb.data.get("count", 0)
            bb.data["count"] = count + 1
            if count < 2:
                return Status.RUNNING
            return Status.SUCCESS

        manager.register_action("increment", increment_action)
        nodes = {"root": Action(id="root", action="increment")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard())

        # Tick 1
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["count"] == 1

        # Tick 2
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["count"] == 2

        # Tick 3
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["count"] == 3
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"

    def test_multiple_entities_separate_blackboards(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def write_id(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["eid"] = eid
            return Status.SUCCESS

        manager.register_action("write", write_id)
        nodes = {"root": Action(id="root", action="write")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid1 = engine.world.spawn()
        eid2 = engine.world.spawn()
        engine.world.attach(eid1, BehaviorTree(tree_name="test"))
        engine.world.attach(eid1, Blackboard())
        engine.world.attach(eid2, BehaviorTree(tree_name="test"))
        engine.world.attach(eid2, Blackboard())

        engine.step()

        bb1 = engine.world.get(eid1, Blackboard)
        bb2 = engine.world.get(eid2, Blackboard)
        assert bb1.data["eid"] == eid1
        assert bb2.data["eid"] == eid2

    def test_blackboard_with_complex_data(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def store_complex(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            bb.data["position"] = (10, 20)
            bb.data["inventory"] = ["sword", "shield"]
            bb.data["stats"] = {"hp": 100, "mana": 50}
            return Status.SUCCESS

        manager.register_action("store", store_complex)
        nodes = {"root": Action(id="root", action="store")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard())

        engine.step()

        bb = engine.world.get(eid, Blackboard)
        assert bb.data["position"] == (10, 20)
        assert bb.data["inventory"] == ["sword", "shield"]
        assert bb.data["stats"] == {"hp": 100, "mana": 50}

    def test_blackboard_without_component_raises(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def read_action(world, ctx, eid):
            bb = world.get(eid, Blackboard)  # Will raise if not attached
            return Status.SUCCESS

        manager.register_action("read", read_action)
        nodes = {"root": Action(id="root", action="read")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        # No Blackboard attached

        with pytest.raises(Exception):  # World.get raises if component not found
            engine.step()

    def test_blackboard_data_modification(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def modify_action(world, ctx, eid):
            bb = world.get(eid, Blackboard)
            if "value" not in bb.data:
                bb.data["value"] = 10
            else:
                bb.data["value"] *= 2
            return Status.SUCCESS

        manager.register_action("modify", modify_action)
        nodes = {"root": Action(id="root", action="modify")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard())

        # Tick 1
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["value"] == 10

        # Tick 2
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["value"] == 20

        # Tick 3
        engine.step()
        bb = engine.world.get(eid, Blackboard)
        assert bb.data["value"] == 40

    def test_condition_writes_blackboard(self):
        # Unusual but valid: condition can have side effects
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        def write_condition(world, eid):
            bb = world.get(eid, Blackboard)
            bb.data["checked"] = True
            return True

        manager.register_condition("write", write_condition)
        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)

        nodes = {
            "root": Sequence(id="root", children=("cond", "act")),
            "cond": Condition(id="cond", condition="write"),
            "act": Action(id="act", action="succeed"),
        }
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))
        engine.world.attach(eid, Blackboard())

        engine.step()

        bb = engine.world.get(eid, Blackboard)
        assert bb.data["checked"] is True
