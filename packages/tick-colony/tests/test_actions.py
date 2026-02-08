"""Tests for tick_colony.actions module - multi-tick tasks."""

import pytest
from tick_colony import Action, make_action_system
from tick import Engine


class TestAction:
    def test_action_creation_with_defaults(self):
        action = Action(name="gather_wood", total_ticks=10)
        assert action.name == "gather_wood"
        assert action.total_ticks == 10
        assert action.elapsed_ticks == 0
        assert action.cancelled is False

    def test_action_creation_with_elapsed(self):
        action = Action(name="build", total_ticks=20, elapsed_ticks=5)
        assert action.elapsed_ticks == 5

    def test_action_creation_cancelled(self):
        action = Action(name="mine", total_ticks=15, cancelled=True)
        assert action.cancelled is True


class TestActionSystem:
    def test_action_progress_over_ticks(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="work", total_ticks=5))

        completed_actions = []

        def on_complete(world, ctx, entity_id, action):
            completed_actions.append((entity_id, action.name, ctx.tick_number))

        action_system = make_action_system(on_complete=on_complete)
        engine.add_system(action_system)

        # Run 4 ticks - action not complete yet
        for _ in range(4):
            engine.step()
            action_comp = world.get(e1, Action)
            assert action_comp.elapsed_ticks <= 4

        # 5th tick should complete
        engine.step()
        assert len(completed_actions) == 1
        assert completed_actions[0] == (e1, "work", 5)
        assert not world.has(e1, Action)  # Action detached

    def test_action_complete_callback_fires_when_elapsed_equals_total(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="task", total_ticks=3, elapsed_ticks=2))

        completed = []

        def on_complete(world, ctx, entity_id, action):
            completed.append(entity_id)

        action_system = make_action_system(on_complete=on_complete)
        engine.add_system(action_system)

        engine.step()  # elapsed becomes 3, equals total
        assert len(completed) == 1
        assert not world.has(e1, Action)

    def test_action_detached_after_completion(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="fast", total_ticks=1))

        def on_complete(world, ctx, entity_id, action):
            pass

        action_system = make_action_system(on_complete=on_complete)
        engine.add_system(action_system)

        assert world.has(e1, Action)
        engine.step()
        assert not world.has(e1, Action)

    def test_cancelled_action_fires_on_cancel(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        action = Action(name="cancelled_task", total_ticks=10, elapsed_ticks=3)
        world.attach(e1, action)

        cancelled_actions = []

        def on_complete(world, ctx, entity_id, action):
            pass  # Should not be called

        def on_cancel(world, ctx, entity_id, action):
            cancelled_actions.append((entity_id, action.name, action.elapsed_ticks))

        action_system = make_action_system(on_complete=on_complete, on_cancel=on_cancel)
        engine.add_system(action_system)

        # Cancel the action
        action.cancelled = True
        engine.step()

        assert len(cancelled_actions) == 1
        assert cancelled_actions[0] == (e1, "cancelled_task", 3)
        assert not world.has(e1, Action)

    def test_cancelled_action_detached(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="cancel_me", total_ticks=10, cancelled=True))

        def on_cancel(world, ctx, entity_id, action):
            pass

        action_system = make_action_system(on_complete=lambda *_: None, on_cancel=on_cancel)
        engine.add_system(action_system)

        assert world.has(e1, Action)
        engine.step()
        assert not world.has(e1, Action)

    def test_action_with_no_on_cancel_silent(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="silent_cancel", total_ticks=5, cancelled=True))

        action_system = make_action_system(on_complete=lambda *_: None)  # No on_cancel
        engine.add_system(action_system)

        engine.step()  # Should not raise
        assert not world.has(e1, Action)

    def test_multiple_entities_with_actions(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        e2 = world.spawn()
        e3 = world.spawn()

        world.attach(e1, Action(name="a1", total_ticks=2))
        world.attach(e2, Action(name="a2", total_ticks=3))
        world.attach(e3, Action(name="a3", total_ticks=1))

        completed = []

        def on_complete(world, ctx, entity_id, action):
            completed.append((ctx.tick_number, entity_id, action.name))

        action_system = make_action_system(on_complete=on_complete)
        engine.add_system(action_system)

        engine.step()  # tick 1: e3 completes
        assert len(completed) == 1
        assert completed[0] == (1, e3, "a3")

        engine.step()  # tick 2: e1 completes
        assert len(completed) == 2
        assert (2, e1, "a1") in completed

        engine.step()  # tick 3: e2 completes
        assert len(completed) == 3
        assert (3, e2, "a2") in completed

    def test_action_system_with_no_actions(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        world.spawn()  # Entity with no action

        action_system = make_action_system(on_complete=lambda *_: None)
        engine.add_system(action_system)

        engine.step()  # Should not crash

    def test_action_callback_receives_correct_parameters(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="verify_params", total_ticks=1))

        received_params = []

        def on_complete(world_arg, ctx_arg, eid_arg, action_arg):
            received_params.append({
                "world": world_arg,
                "ctx": ctx_arg,
                "entity_id": eid_arg,
                "action": action_arg,
            })

        action_system = make_action_system(on_complete=on_complete)
        engine.add_system(action_system)

        engine.step()

        assert len(received_params) == 1
        params = received_params[0]
        assert params["world"] is world
        assert params["ctx"].tick_number == 1
        assert params["entity_id"] == e1
        assert params["action"].name == "verify_params"

    def test_action_not_incremented_if_cancelled(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        world.attach(e1, Action(name="cancel_early", total_ticks=10, elapsed_ticks=2, cancelled=True))

        def on_cancel(world, ctx, entity_id, action):
            # Verify elapsed hasn't been incremented
            assert action.elapsed_ticks == 2

        action_system = make_action_system(on_complete=lambda *_: None, on_cancel=on_cancel)
        engine.add_system(action_system)

        engine.step()
