"""Tests for behavior tree system."""
import random

import pytest

from tick import Engine
from tick_ai.components import BehaviorTree
from tick_ai.manager import AIManager
from tick_ai.nodes import Action, Selector, Sequence, Status
from tick_ai.systems import make_bt_system


class TestBTSystem:
    """Test make_bt_system factory."""

    def test_system_evaluates_tree(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)
        nodes = {"root": Action(id="root", action="succeed")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"
        assert bt.running_node == ""

    def test_system_handles_running_state(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("run", lambda w, c, e: Status.RUNNING)
        nodes = {"root": Action(id="root", action="run")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "running"
        assert bt.running_node == "root"

    def test_system_resumes_running_tree(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        tick_count = [0]

        def run_twice(w, c, e):
            tick_count[0] += 1
            if tick_count[0] < 3:
                return Status.RUNNING
            return Status.SUCCESS

        manager.register_action("run", run_twice)
        nodes = {"root": Action(id="root", action="run")}
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        # Tick 1
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "running"

        # Tick 2
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "running"

        # Tick 3
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"

    def test_system_tree_not_found(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="missing"))

        # Should not crash
        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == ""

    def test_on_status_callback_success(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)
        nodes = {"root": Action(id="root", action="succeed")}
        manager.define_tree("test", "root", nodes)

        calls = []

        def on_status(world, ctx, eid, status):
            calls.append((eid, status))

        system = make_bt_system(manager, on_status=on_status)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        engine.step()

        assert len(calls) == 1
        assert calls[0] == (eid, "success")

    def test_on_status_callback_failure(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("fail", lambda w, c, e: Status.FAILURE)
        nodes = {"root": Action(id="root", action="fail")}
        manager.define_tree("test", "root", nodes)

        calls = []

        def on_status(world, ctx, eid, status):
            calls.append((eid, status))

        system = make_bt_system(manager, on_status=on_status)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        engine.step()

        assert len(calls) == 1
        assert calls[0] == (eid, "failure")

    def test_on_status_not_called_for_running(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("run", lambda w, c, e: Status.RUNNING)
        nodes = {"root": Action(id="root", action="run")}
        manager.define_tree("test", "root", nodes)

        calls = []

        def on_status(world, ctx, eid, status):
            calls.append((eid, status))

        system = make_bt_system(manager, on_status=on_status)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        engine.step()
        engine.step()

        # Should not be called for running status
        assert len(calls) == 0

    def test_multiple_entities(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)
        manager.register_action("fail", lambda w, c, e: Status.FAILURE)
        nodes1 = {"root": Action(id="root", action="succeed")}
        nodes2 = {"root": Action(id="root", action="fail")}
        manager.define_tree("tree1", "root", nodes1)
        manager.define_tree("tree2", "root", nodes2)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid1 = engine.world.spawn()
        eid2 = engine.world.spawn()
        engine.world.attach(eid1, BehaviorTree(tree_name="tree1"))
        engine.world.attach(eid2, BehaviorTree(tree_name="tree2"))

        engine.step()

        bt1 = engine.world.get(eid1, BehaviorTree)
        bt2 = engine.world.get(eid2, BehaviorTree)
        assert bt1.status == "success"
        assert bt2.status == "failure"

    def test_system_updates_repeat_counts(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        from tick_ai.nodes import Repeater

        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)
        nodes = {
            "root": Repeater(id="root", child="a", max_count=3),
            "a": Action(id="a", action="succeed"),
        }
        manager.define_tree("test", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        # Tick 1
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.repeat_counts == {"root": 1}

        # Tick 2
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.repeat_counts == {"root": 2}

        # Tick 3
        engine.step()
        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"
        assert bt.repeat_counts == {}

    def test_system_with_complex_tree(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

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
        manager.define_tree("complex", "root", nodes)

        system = make_bt_system(manager)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="complex"))

        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"

    def test_system_without_callback(self):
        engine = Engine(tps=10, seed=42)
        manager = AIManager()

        manager.register_action("succeed", lambda w, c, e: Status.SUCCESS)
        nodes = {"root": Action(id="root", action="succeed")}
        manager.define_tree("test", "root", nodes)

        # No on_status callback
        system = make_bt_system(manager, on_status=None)
        engine.add_system(system)

        eid = engine.world.spawn()
        engine.world.attach(eid, BehaviorTree(tree_name="test"))

        # Should not crash
        engine.step()

        bt = engine.world.get(eid, BehaviorTree)
        assert bt.status == "success"
