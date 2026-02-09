"""Tests for change detection hooks (on_attach, on_detach, off_attach, off_detach)."""

from dataclasses import dataclass

import pytest

from tick.types import DeadEntityError
from tick.world import World


@dataclass
class Position:
    x: float
    y: float


@dataclass
class Velocity:
    dx: float
    dy: float


@dataclass
class Health:
    hp: int


# --- on_attach ---


def test_on_attach_fires_after_attach():
    world = World()
    eid = world.spawn()
    calls = []

    def callback(w, e, c):
        calls.append((e, c))

    world.on_attach(Position, callback)
    pos = Position(1.0, 2.0)
    world.attach(eid, pos)

    assert len(calls) == 1
    assert calls[0] == (eid, pos)


def test_on_attach_component_accessible_in_callback():
    world = World()
    eid = world.spawn()
    retrieved = []

    def callback(w, e, c):
        # Component should be accessible via world.get() inside callback
        retrieved_comp = w.get(e, Position)
        retrieved.append(retrieved_comp)

    world.on_attach(Position, callback)
    pos = Position(3.0, 4.0)
    world.attach(eid, pos)

    assert len(retrieved) == 1
    assert retrieved[0] is pos


def test_on_attach_receives_correct_args():
    world = World()
    eid = world.spawn()
    captured = []

    def callback(w, e, c):
        captured.append((w, e, c))

    world.on_attach(Position, callback)
    pos = Position(5.0, 6.0)
    world.attach(eid, pos)

    assert len(captured) == 1
    w, e, c = captured[0]
    assert w is world
    assert e == eid
    assert c is pos


def test_on_attach_multiple_hooks_for_same_type():
    world = World()
    eid = world.spawn()
    calls1 = []
    calls2 = []
    calls3 = []

    world.on_attach(Position, lambda w, e, c: calls1.append(e))
    world.on_attach(Position, lambda w, e, c: calls2.append(e))
    world.on_attach(Position, lambda w, e, c: calls3.append(e))

    world.attach(eid, Position(0.0, 0.0))

    assert calls1 == [eid]
    assert calls2 == [eid]
    assert calls3 == [eid]


def test_on_attach_only_fires_for_matching_type():
    world = World()
    eid = world.spawn()
    position_calls = []
    velocity_calls = []

    world.on_attach(Position, lambda w, e, c: position_calls.append(e))
    world.on_attach(Velocity, lambda w, e, c: velocity_calls.append(e))

    world.attach(eid, Position(1.0, 1.0))

    assert len(position_calls) == 1
    assert len(velocity_calls) == 0

    world.attach(eid, Velocity(2.0, 2.0))

    assert len(position_calls) == 1
    assert len(velocity_calls) == 1


def test_on_attach_fires_on_replace():
    world = World()
    eid = world.spawn()
    calls = []

    world.on_attach(Position, lambda w, e, c: calls.append(c))

    pos1 = Position(1.0, 1.0)
    world.attach(eid, pos1)

    pos2 = Position(2.0, 2.0)
    world.attach(eid, pos2)

    assert len(calls) == 2
    assert calls[0] is pos1
    assert calls[1] is pos2


def test_on_attach_does_not_fire_during_restore():
    world = World()
    world.register_component(Position)
    calls = []

    world.on_attach(Position, lambda w, e, c: calls.append(e))

    # Create and snapshot
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    snapshot = world.snapshot()

    # Clear and restore
    world2 = World()
    world2.register_component(Position)
    world2.on_attach(Position, lambda w, e, c: calls.append(e))
    world2.restore(snapshot)

    # Only the initial attach should have fired, not the restore
    assert len(calls) == 1
    assert calls[0] == eid


# --- on_detach ---


def test_on_detach_fires_after_detach():
    world = World()
    eid = world.spawn()
    pos = Position(1.0, 2.0)
    world.attach(eid, pos)

    calls = []
    world.on_detach(Position, lambda w, e, c: calls.append((e, c)))

    world.detach(eid, Position)

    assert len(calls) == 1
    assert calls[0] == (eid, pos)


def test_on_detach_component_not_accessible_after():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(3.0, 4.0))

    has_component_in_callback = []

    def callback(w, e, c):
        # Component should already be detached
        has_component_in_callback.append(w.has(e, Position))

    world.on_detach(Position, callback)
    world.detach(eid, Position)

    assert len(has_component_in_callback) == 1
    assert has_component_in_callback[0] is False


def test_on_detach_receives_removed_component():
    world = World()
    eid = world.spawn()
    pos = Position(5.0, 6.0)
    world.attach(eid, pos)

    captured = []
    world.on_detach(Position, lambda w, e, c: captured.append(c))

    world.detach(eid, Position)

    assert len(captured) == 1
    assert captured[0] is pos
    assert captured[0].x == 5.0
    assert captured[0].y == 6.0


def test_on_detach_multiple_hooks_for_same_type():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))

    calls1 = []
    calls2 = []
    calls3 = []

    world.on_detach(Position, lambda w, e, c: calls1.append(e))
    world.on_detach(Position, lambda w, e, c: calls2.append(e))
    world.on_detach(Position, lambda w, e, c: calls3.append(e))

    world.detach(eid, Position)

    assert calls1 == [eid]
    assert calls2 == [eid]
    assert calls3 == [eid]


def test_on_detach_only_fires_for_matching_type():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 1.0))
    world.attach(eid, Velocity(2.0, 2.0))

    position_calls = []
    velocity_calls = []

    world.on_detach(Position, lambda w, e, c: position_calls.append(e))
    world.on_detach(Velocity, lambda w, e, c: velocity_calls.append(e))

    world.detach(eid, Position)

    assert len(position_calls) == 1
    assert len(velocity_calls) == 0


def test_on_detach_does_not_fire_for_nonexistent_component():
    world = World()
    eid = world.spawn()

    calls = []
    world.on_detach(Position, lambda w, e, c: calls.append(e))

    # Detach component that was never attached
    world.detach(eid, Position)

    assert len(calls) == 0


def test_on_detach_does_not_fire_during_restore():
    world = World()
    world.register_component(Position)

    # Create entity with component
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    snapshot = world.snapshot()

    # Add hook after snapshot
    calls = []
    world.on_detach(Position, lambda w, e, c: calls.append(e))

    # Restore (which clears components)
    world.restore(snapshot)

    # Hook should not have fired during restore
    assert len(calls) == 0


# --- despawn triggers on_detach ---


def test_despawn_fires_on_detach_for_each_component():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.attach(eid, Velocity(3.0, 4.0))
    world.attach(eid, Health(100))

    position_calls = []
    velocity_calls = []
    health_calls = []

    world.on_detach(Position, lambda w, e, c: position_calls.append((e, c)))
    world.on_detach(Velocity, lambda w, e, c: velocity_calls.append((e, c)))
    world.on_detach(Health, lambda w, e, c: health_calls.append((e, c)))

    world.despawn(eid)

    assert len(position_calls) == 1
    assert len(velocity_calls) == 1
    assert len(health_calls) == 1


def test_despawn_entity_not_alive_in_detach_callback():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))

    alive_in_callback = []

    def callback(w, e, c):
        alive_in_callback.append(w.alive(e))

    world.on_detach(Position, callback)
    world.despawn(eid)

    assert len(alive_in_callback) == 1
    assert alive_in_callback[0] is False


def test_despawn_on_detach_receives_correct_components():
    world = World()
    eid = world.spawn()
    pos = Position(7.0, 8.0)
    vel = Velocity(9.0, 10.0)
    world.attach(eid, pos)
    world.attach(eid, vel)

    captured = []

    def capture_position(w, e, c):
        captured.append(("Position", c))

    def capture_velocity(w, e, c):
        captured.append(("Velocity", c))

    world.on_detach(Position, capture_position)
    world.on_detach(Velocity, capture_velocity)

    world.despawn(eid)

    assert len(captured) == 2
    # Order may vary based on dict iteration
    types_captured = {t for t, _ in captured}
    assert types_captured == {"Position", "Velocity"}


# --- off_attach / off_detach ---


def test_off_attach_removes_callback():
    world = World()
    eid = world.spawn()

    calls = []

    def callback(w, e, c):
        calls.append(e)

    world.on_attach(Position, callback)
    world.attach(eid, Position(1.0, 1.0))
    assert len(calls) == 1

    world.off_attach(Position, callback)
    eid2 = world.spawn()
    world.attach(eid2, Position(2.0, 2.0))
    assert len(calls) == 1  # Should not increment


def test_off_detach_removes_callback():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 1.0))

    calls = []

    def callback(w, e, c):
        calls.append(e)

    world.on_detach(Position, callback)
    world.detach(eid, Position)
    assert len(calls) == 1

    world.attach(eid, Position(2.0, 2.0))
    world.off_detach(Position, callback)
    world.detach(eid, Position)
    assert len(calls) == 1  # Should not increment


def test_off_attach_nonexistent_callback_is_noop():
    world = World()

    def callback(w, e, c):
        pass

    # Removing callback that was never registered should not raise
    world.off_attach(Position, callback)

    # Should still work normally
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))


def test_off_detach_nonexistent_callback_is_noop():
    world = World()

    def callback(w, e, c):
        pass

    # Removing callback that was never registered should not raise
    world.off_detach(Position, callback)

    # Should still work normally
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))
    world.detach(eid, Position)


def test_off_attach_removes_only_specified_callback():
    world = World()
    eid = world.spawn()

    calls1 = []
    calls2 = []

    def callback1(w, e, c):
        calls1.append(e)

    def callback2(w, e, c):
        calls2.append(e)

    world.on_attach(Position, callback1)
    world.on_attach(Position, callback2)

    world.off_attach(Position, callback1)

    world.attach(eid, Position(1.0, 1.0))

    assert len(calls1) == 0
    assert len(calls2) == 1


def test_off_detach_removes_only_specified_callback():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 1.0))

    calls1 = []
    calls2 = []

    def callback1(w, e, c):
        calls1.append(e)

    def callback2(w, e, c):
        calls2.append(e)

    world.on_detach(Position, callback1)
    world.on_detach(Position, callback2)

    world.off_detach(Position, callback1)

    world.detach(eid, Position)

    assert len(calls1) == 0
    assert len(calls2) == 1


def test_off_attach_for_nonexistent_type_is_noop():
    world = World()

    def callback(w, e, c):
        pass

    # Type never had any callbacks registered
    world.off_attach(Health, callback)


def test_off_detach_for_nonexistent_type_is_noop():
    world = World()

    def callback(w, e, c):
        pass

    # Type never had any callbacks registered
    world.off_detach(Health, callback)


# --- restore suppression ---


def test_restore_does_not_fire_attach_hooks():
    world = World()
    world.register_component(Position)
    world.register_component(Velocity)

    # Create snapshot with entities
    eid1 = world.spawn()
    eid2 = world.spawn()
    world.attach(eid1, Position(1.0, 2.0))
    world.attach(eid2, Velocity(3.0, 4.0))
    snapshot = world.snapshot()

    # Fresh world with hooks
    world2 = World()
    world2.register_component(Position)
    world2.register_component(Velocity)

    attach_calls = []
    world2.on_attach(Position, lambda w, e, c: attach_calls.append(e))
    world2.on_attach(Velocity, lambda w, e, c: attach_calls.append(e))

    world2.restore(snapshot)

    # No hooks should have fired
    assert len(attach_calls) == 0


def test_restore_does_not_fire_detach_hooks():
    world = World()
    world.register_component(Position)

    # Create world with component
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))

    # Add detach hook
    detach_calls = []
    world.on_detach(Position, lambda w, e, c: detach_calls.append(e))

    # Create empty snapshot
    snapshot = {"entities": [], "next_id": 1, "components": {}}

    # Restore (clears existing components)
    world.restore(snapshot)

    # Detach hook should not have fired
    assert len(detach_calls) == 0


def test_hooks_re_enabled_after_restore():
    world = World()
    world.register_component(Position)

    # Create snapshot
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    snapshot = world.snapshot()

    # Restore
    world.restore(snapshot)

    # Add hook after restore
    attach_calls = []
    world.on_attach(Position, lambda w, e, c: attach_calls.append(e))

    # New attach should fire hook
    eid2 = world.spawn()
    world.attach(eid2, Position(3.0, 4.0))

    assert len(attach_calls) == 1
    assert attach_calls[0] == eid2


def test_hooks_survive_restore():
    world = World()
    world.register_component(Position)

    # Register hooks before snapshot
    attach_calls = []
    detach_calls = []
    world.on_attach(Position, lambda w, e, c: attach_calls.append(e))
    world.on_detach(Position, lambda w, e, c: detach_calls.append(e))

    # Create and restore snapshot
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    snapshot = world.snapshot()
    world.restore(snapshot)

    # Hooks should still be registered (but restore didn't fire them)
    assert len(attach_calls) == 1  # Only the original attach before snapshot

    # New operations should fire hooks
    eid2 = world.spawn()
    world.attach(eid2, Position(3.0, 4.0))
    world.detach(eid2, Position)

    assert len(attach_calls) == 2
    assert len(detach_calls) == 1


# --- edge cases ---


def test_attach_to_dead_entity_raises_before_hooks_fire():
    world = World()
    eid = world.spawn()
    world.despawn(eid)

    calls = []
    world.on_attach(Position, lambda w, e, c: calls.append(e))

    with pytest.raises(DeadEntityError):
        world.attach(eid, Position(0.0, 0.0))

    # Hook should not have fired
    assert len(calls) == 0


def test_detach_nonexistent_component_fires_no_hooks():
    world = World()
    eid = world.spawn()
    # Never attach Position

    calls = []
    world.on_detach(Position, lambda w, e, c: calls.append(e))

    world.detach(eid, Position)

    assert len(calls) == 0


def test_hook_exception_propagates():
    world = World()
    eid = world.spawn()

    def bad_callback(w, e, c):
        raise ValueError("hook error")

    world.on_attach(Position, bad_callback)

    with pytest.raises(ValueError, match="hook error"):
        world.attach(eid, Position(0.0, 0.0))


def test_on_attach_exception_component_still_attached():
    world = World()
    eid = world.spawn()

    def bad_callback(w, e, c):
        raise ValueError("hook error")

    world.on_attach(Position, bad_callback)

    try:
        world.attach(eid, Position(1.0, 2.0))
    except ValueError:
        pass

    # Component should still be attached despite hook error
    assert world.has(eid, Position)
    assert world.get(eid, Position).x == 1.0


def test_on_detach_exception_component_already_detached():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))

    def bad_callback(w, e, c):
        raise ValueError("hook error")

    world.on_detach(Position, bad_callback)

    try:
        world.detach(eid, Position)
    except ValueError:
        pass

    # Component should be detached despite hook error
    assert not world.has(eid, Position)


def test_hook_can_query_world():
    world = World()
    eid1 = world.spawn()
    eid2 = world.spawn()
    world.attach(eid1, Health(100))
    world.attach(eid2, Health(50))

    query_results = []

    def callback(w, e, c):
        # Hook can query world
        entities_with_health = len(list(w.query(Health)))
        query_results.append(entities_with_health)

    world.on_attach(Position, callback)
    world.attach(eid1, Position(0.0, 0.0))

    assert len(query_results) == 1
    assert query_results[0] == 2


def test_hook_can_spawn_entities():
    world = World()
    eid = world.spawn()

    spawned_ids = []

    def callback(w, e, c):
        # Hook can spawn new entities
        new_eid = w.spawn()
        spawned_ids.append(new_eid)

    world.on_attach(Position, callback)
    world.attach(eid, Position(0.0, 0.0))

    assert len(spawned_ids) == 1
    assert world.alive(spawned_ids[0])


def test_hook_can_attach_components():
    world = World()
    eid = world.spawn()

    def callback(w, e, c):
        # Hook can attach components to the same entity
        w.attach(e, Health(100))

    world.on_attach(Position, callback)
    world.attach(eid, Position(0.0, 0.0))

    assert world.has(eid, Health)
    assert world.get(eid, Health).hp == 100


def test_hook_can_detach_other_components():
    world = World()
    eid = world.spawn()
    world.attach(eid, Health(100))

    def callback(w, e, c):
        # Hook can detach other components
        w.detach(e, Health)

    world.on_attach(Position, callback)
    world.attach(eid, Position(0.0, 0.0))

    assert world.has(eid, Position)
    assert not world.has(eid, Health)


def test_multiple_entities_same_hook():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    calls = []
    world.on_attach(Position, lambda w, e, c: calls.append(e))

    world.attach(e1, Position(1.0, 1.0))
    world.attach(e2, Position(2.0, 2.0))
    world.attach(e3, Position(3.0, 3.0))

    assert len(calls) == 3
    assert set(calls) == {e1, e2, e3}


def test_hook_registration_order_matches_execution_order():
    world = World()
    eid = world.spawn()

    order = []

    world.on_attach(Position, lambda w, e, c: order.append(1))
    world.on_attach(Position, lambda w, e, c: order.append(2))
    world.on_attach(Position, lambda w, e, c: order.append(3))

    world.attach(eid, Position(0.0, 0.0))

    assert order == [1, 2, 3]
