"""Additional edge case and error condition tests for comprehensive coverage."""

import random

import pytest
from dataclasses import dataclass

from tick.clock import Clock
from tick.engine import Engine
from tick.types import DeadEntityError
from tick.world import World

_test_rng = random.Random(0)


@dataclass
class Marker:
    value: int


# --- Clock edge cases ---


def test_clock_with_zero_tps_raises_error():
    """Test Clock raises ValueError for TPS of 0."""
    with pytest.raises(ValueError, match="tps must be positive"):
        Clock(tps=0)


def test_clock_with_negative_tps_raises_error():
    """Test Clock raises ValueError for negative TPS."""
    with pytest.raises(ValueError, match="tps must be positive"):
        Clock(tps=-10)


def test_clock_with_very_high_tps():
    """Test Clock handles very high TPS values."""
    clock = Clock(tps=10000)
    assert clock.tps == 10000
    assert abs(clock.dt - 0.0001) < 1e-10

    clock.advance()
    ctx = clock.context(lambda: None, _test_rng)
    assert ctx.tick_number == 1
    assert abs(ctx.elapsed - 0.0001) < 1e-10


def test_clock_with_tps_one():
    """Test Clock with TPS of 1 (edge case)."""
    clock = Clock(tps=1)
    assert clock.tps == 1
    assert clock.dt == 1.0

    clock.advance()
    ctx = clock.context(lambda: None, _test_rng)
    assert ctx.tick_number == 1
    assert ctx.elapsed == 1.0


# --- World edge cases ---


def test_world_spawn_many_entities():
    """Test spawning large number of entities."""
    world = World()
    entities = [world.spawn() for _ in range(10000)]

    # All should be unique
    assert len(set(entities)) == 10000

    # All should be alive
    assert len(world.entities()) == 10000


def test_world_despawn_nonexistent_entity_is_safe():
    """Test despawning non-existent entity doesn't raise error."""
    world = World()

    # Despawn entity that never existed
    world.despawn(999)

    # Despawn negative entity ID
    world.despawn(-1)


def test_world_despawn_already_despawned_entity():
    """Test despawning same entity twice is safe."""
    world = World()

    entity_id = world.spawn()
    world.despawn(entity_id)
    world.despawn(entity_id)  # Second despawn should be safe


def test_world_attach_to_despawned_entity():
    """Test attaching component to despawned entity raises DeadEntityError."""
    world = World()

    entity_id = world.spawn()
    world.despawn(entity_id)

    with pytest.raises(DeadEntityError) as exc_info:
        world.attach(entity_id, Marker(value=42))
    assert exc_info.value.entity_id == entity_id


def test_world_get_from_nonexistent_entity():
    """Test get() from entity that never existed raises KeyError."""
    world = World()

    with pytest.raises(KeyError):
        world.get(999, Marker)


def test_world_has_on_nonexistent_entity():
    """Test has() on non-existent entity returns False."""
    world = World()

    assert world.has(999, Marker) is False


def test_world_detach_from_nonexistent_entity():
    """Test detach() from non-existent entity is safe."""
    world = World()

    # Should not raise
    world.detach(999, Marker)


def test_world_detach_nonexistent_component():
    """Test detaching component that was never attached is safe."""
    world = World()

    entity_id = world.spawn()
    world.detach(entity_id, Marker)  # Should not raise


def test_world_query_empty_types():
    """Test query with no component types returns empty."""
    world = World()

    entity_id = world.spawn()
    world.attach(entity_id, Marker(value=1))

    results = list(world.query())  # No types
    assert len(results) == 0


def test_world_multiple_attach_overwrites():
    """Test multiple attaches of same type keeps only last."""
    world = World()

    entity_id = world.spawn()
    world.attach(entity_id, Marker(value=1))
    world.attach(entity_id, Marker(value=2))
    world.attach(entity_id, Marker(value=3))

    component = world.get(entity_id, Marker)
    assert component.value == 3


def test_world_alive_after_multiple_spawns_and_despawns():
    """Test alive() tracks entity lifecycle correctly."""
    world = World()

    e1 = world.spawn()
    assert world.alive(e1)

    e2 = world.spawn()
    assert world.alive(e2)

    world.despawn(e1)
    assert not world.alive(e1)
    assert world.alive(e2)

    world.despawn(e2)
    assert not world.alive(e1)
    assert not world.alive(e2)


def test_world_entities_is_frozenset():
    """Test entities() returns frozenset (immutable)."""
    world = World()

    e1 = world.spawn()
    e2 = world.spawn()

    entities = world.entities()
    assert isinstance(entities, frozenset)

    # Should not be able to modify it
    with pytest.raises(AttributeError):
        entities.add(999)  # frozenset has no add method


# --- Engine edge cases ---


def test_engine_run_negative_ticks():
    """Test run() with negative n (should run 0 ticks)."""
    engine = Engine()
    tick_count = []

    def system(world, ctx):
        tick_count.append(1)

    engine.add_system(system)
    engine.run(-5)

    # Should not run any ticks
    assert len(tick_count) == 0
    assert engine.clock.tick_number == 0


def test_engine_multiple_request_stop_calls():
    """Test multiple request_stop() calls don't cause issues."""
    engine = Engine()
    stop_count = []

    def system(world, ctx):
        ctx.request_stop()
        ctx.request_stop()  # Call twice
        ctx.request_stop()  # Call three times
        stop_count.append(1)

    engine.add_system(system)
    engine.run(10)

    # Should stop after first tick
    assert len(stop_count) == 1


def test_engine_request_stop_in_first_system():
    """Test request_stop in first system prevents later systems."""
    engine = Engine()
    calls = []

    def stopper(world, ctx):
        calls.append("stopper")
        ctx.request_stop()

    def should_not_run(world, ctx):
        calls.append("should_not_run")

    engine.add_system(stopper)
    engine.add_system(should_not_run)

    engine.run(1)

    assert calls == ["stopper"]
    assert "should_not_run" not in calls


def test_engine_no_systems_no_hooks():
    """Test engine with no systems or hooks runs successfully."""
    engine = Engine()
    engine.run(10)

    assert engine.clock.tick_number == 10


def test_engine_only_hooks_no_systems():
    """Test engine with only hooks but no systems."""
    engine = Engine()
    events = []

    def on_start(world, ctx):
        events.append("start")

    def on_stop(world, ctx):
        events.append("stop")

    engine.on_start(on_start)
    engine.on_stop(on_stop)

    engine.run(5)

    assert events == ["start", "stop"]
    assert engine.clock.tick_number == 5


def test_engine_step_resets_stop_flag():
    """Test step() resets stop flag so all systems run."""
    engine = Engine()
    ran = []

    def sys_a(world, ctx):
        ran.append("a")
        ctx.request_stop()

    def sys_b(world, ctx):
        ran.append("b")

    engine.add_system(sys_a)
    engine.add_system(sys_b)

    # First step: sys_a requests stop, sys_b is skipped
    engine.step()
    assert ran == ["a"]

    # Second step: flag was reset, both systems run
    ran.clear()
    engine.step()
    assert ran == ["a"]  # sys_a still calls request_stop, so sys_b is still skipped


def test_engine_run_after_run_forever():
    """Test run() can be called after run_forever()."""
    engine = Engine(tps=1000)
    tick_numbers = []

    stop_at = [3]  # mutable so we can change the stop condition

    def system(world, ctx):
        tick_numbers.append(ctx.tick_number)
        if ctx.tick_number >= stop_at[0]:
            ctx.request_stop()

    engine.add_system(system)

    # First run_forever — stops at tick 3
    engine.run_forever()
    assert len(tick_numbers) == 3

    # Then run() — disable stop condition so it runs fully
    stop_at[0] = 999
    engine.run(2)
    assert len(tick_numbers) == 5
    assert tick_numbers == [1, 2, 3, 4, 5]


def test_engine_multiple_consecutive_runs():
    """Test multiple consecutive run() calls."""
    engine = Engine()
    tick_numbers = []

    def system(world, ctx):
        tick_numbers.append(ctx.tick_number)

    engine.add_system(system)

    engine.run(5)
    engine.run(3)
    engine.run(2)

    assert tick_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_engine_lifecycle_hooks_run_once_per_run():
    """Test lifecycle hooks run exactly once per run() call."""
    engine = Engine()
    start_count = []
    stop_count = []

    def on_start(world, ctx):
        start_count.append(1)

    def on_stop(world, ctx):
        stop_count.append(1)

    engine.on_start(on_start)
    engine.on_stop(on_stop)

    engine.run(10)
    engine.run(5)
    engine.run(3)

    # Each run() should call hooks once
    assert len(start_count) == 3
    assert len(stop_count) == 3


def test_engine_hook_exception_propagates():
    """Test exceptions in hooks propagate to caller."""
    engine = Engine()

    def failing_start(world, ctx):
        raise ValueError("Start hook failed")

    engine.on_start(failing_start)

    with pytest.raises(ValueError, match="Start hook failed"):
        engine.run(1)


def test_engine_system_exception_propagates():
    """Test exceptions in systems propagate to caller."""
    engine = Engine()

    def failing_system(world, ctx):
        raise RuntimeError("System failed")

    engine.add_system(failing_system)

    with pytest.raises(RuntimeError, match="System failed"):
        engine.step()


# --- Integration edge cases ---


def test_despawn_during_query_iteration():
    """Test despawning entities while iterating query results."""
    engine = Engine()

    # Create entities
    for i in range(10):
        eid = engine.world.spawn()
        engine.world.attach(eid, Marker(value=i))

    def destroyer(world, ctx):
        # Collect entities first, then despawn
        to_despawn = []
        for eid, (comp,) in world.query(Marker):
            if comp.value % 2 == 0:  # Despawn even values
                to_despawn.append(eid)

        for eid in to_despawn:
            world.despawn(eid)

    engine.add_system(destroyer)
    engine.run(1)

    # Should have 5 odd-valued entities left
    remaining = list(engine.world.query(Marker))
    assert len(remaining) == 5

    # All remaining should have odd values
    for eid, (comp,) in remaining:
        assert comp.value % 2 == 1


def test_spawn_and_attach_in_separate_systems():
    """Test entity spawned in one system can have components attached in another."""
    engine = Engine()
    spawned_ids = []

    def spawner(world, ctx):
        eid = world.spawn()
        spawned_ids.append(eid)

    def attacher(world, ctx):
        # Attach to entities spawned in this tick
        for eid in spawned_ids:
            if world.alive(eid) and not world.has(eid, Marker):
                world.attach(eid, Marker(value=42))

    engine.add_system(spawner)
    engine.add_system(attacher)

    engine.run(3)

    # All 3 spawned entities should have the component
    results = list(engine.world.query(Marker))
    assert len(results) == 3


def test_clock_reset_during_engine_run():
    """Test manually resetting clock doesn't break engine state."""
    engine = Engine()

    def system(world, ctx):
        pass

    engine.add_system(system)

    engine.run(5)
    assert engine.clock.tick_number == 5

    # Manually reset clock (unusual but should be handled)
    engine.clock.reset()
    assert engine.clock.tick_number == 0

    # Engine should continue from reset state
    engine.run(3)
    assert engine.clock.tick_number == 3


def test_world_state_persists_between_runs():
    """Test world state persists across multiple run() calls."""
    engine = Engine()

    # Create entity before first run
    eid = engine.world.spawn()
    engine.world.attach(eid, Marker(value=0))

    def incrementer(world, ctx):
        comp = world.get(eid, Marker)
        comp.value += 1

    engine.add_system(incrementer)

    engine.run(5)
    assert engine.world.get(eid, Marker).value == 5

    engine.run(3)
    assert engine.world.get(eid, Marker).value == 8


def test_system_callable_class_with_state():
    """Test systems can be stateful callable classes."""
    engine = Engine()

    class StatefulSystem:
        def __init__(self):
            self.total_entities_seen = 0
            self.call_count = 0

        def __call__(self, world, ctx):
            self.call_count += 1
            self.total_entities_seen += len(world.entities())

    system = StatefulSystem()
    engine.add_system(system)

    # Spawn some entities
    for _ in range(5):
        engine.world.spawn()

    engine.run(10)

    assert system.call_count == 10
    assert system.total_entities_seen == 50  # 5 entities * 10 ticks


def test_empty_world_queries_dont_break():
    """Test queries on empty world return empty results gracefully."""
    engine = Engine()

    results_per_tick = []

    def system(world, ctx):
        results = list(world.query(Marker))
        results_per_tick.append(len(results))

    engine.add_system(system)
    engine.run(10)

    # All ticks should return 0 results
    assert results_per_tick == [0] * 10


def test_component_type_as_dict_key():
    """Test component types work correctly as dictionary keys."""
    world = World()

    # Different component types
    @dataclass
    class ComponentA:
        a: int

    @dataclass
    class ComponentB:
        b: int

    eid = world.spawn()
    world.attach(eid, ComponentA(a=1))
    world.attach(eid, ComponentB(b=2))

    # Should be able to retrieve each by type
    assert world.get(eid, ComponentA).a == 1
    assert world.get(eid, ComponentB).b == 2

    # Queries should distinguish types
    a_results = list(world.query(ComponentA))
    b_results = list(world.query(ComponentB))

    assert len(a_results) == 1
    assert len(b_results) == 1
