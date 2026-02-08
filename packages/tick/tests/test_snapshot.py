"""Tests for snapshot/restore serialization."""

import json
from dataclasses import dataclass

import pytest

from tick.engine import Engine
from tick.types import SnapshotError, TickContext
from tick.world import World


@dataclass
class Position:
    x: float
    y: float


@dataclass
class Health:
    hp: int


@dataclass
class Tag:
    label: str


# --- Engine snapshot/restore round-trip ---


def test_engine_snapshot_round_trip():
    """Snapshot and restore preserves tick number, RNG state, world."""
    engine = Engine(tps=20, seed=42)
    eid = engine.world.spawn()
    engine.world.attach(eid, Position(1.0, 2.0))
    engine.run(10)

    snap = engine.snapshot()

    engine2 = Engine(tps=20, seed=42)
    engine2.world.register_component(Position)
    engine2.restore(snap)

    assert engine2.clock.tick_number == 10
    assert engine2.seed == 42
    pos = engine2.world.get(eid, Position)
    assert pos.x == 1.0
    assert pos.y == 2.0


def test_engine_snapshot_is_json_compatible():
    """Snapshot can be serialized to JSON and back."""
    engine = Engine(tps=20, seed=42)
    eid = engine.world.spawn()
    engine.world.attach(eid, Position(3.0, 4.0))
    engine.run(5)

    snap = engine.snapshot()
    json_str = json.dumps(snap)
    restored_data = json.loads(json_str)

    engine2 = Engine(tps=20, seed=42)
    engine2.world.register_component(Position)
    engine2.restore(restored_data)

    assert engine2.clock.tick_number == 5
    pos = engine2.world.get(eid, Position)
    assert pos.x == 3.0
    assert pos.y == 4.0


def test_snapshot_contains_version():
    """Snapshot includes version field."""
    engine = Engine(tps=20, seed=1)
    snap = engine.snapshot()
    assert "version" in snap
    assert snap["version"] == 1


def test_snapshot_contains_seed():
    """Snapshot includes the seed."""
    engine = Engine(tps=20, seed=777)
    snap = engine.snapshot()
    assert snap["seed"] == 777


def test_snapshot_contains_rng_state():
    """Snapshot includes RNG state."""
    engine = Engine(tps=20, seed=42)
    engine.run(10)
    snap = engine.snapshot()
    assert "rng_state" in snap
    assert isinstance(snap["rng_state"], list)


# --- World snapshot/restore round-trip ---


def test_world_snapshot_round_trip():
    """World snapshot captures entities and components."""
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    world.attach(e1, Position(1.0, 2.0))
    world.attach(e1, Health(100))
    world.attach(e2, Position(3.0, 4.0))

    snap = world.snapshot()

    world2 = World()
    world2.register_component(Position)
    world2.register_component(Health)
    world2.restore(snap)

    assert world2.alive(e1)
    assert world2.alive(e2)
    pos1 = world2.get(e1, Position)
    assert pos1.x == 1.0 and pos1.y == 2.0
    h1 = world2.get(e1, Health)
    assert h1.hp == 100
    pos2 = world2.get(e2, Position)
    assert pos2.x == 3.0 and pos2.y == 4.0


def test_world_snapshot_preserves_next_id():
    """World snapshot preserves next_id so new spawns don't collide."""
    world = World()
    world.spawn()  # 0
    world.spawn()  # 1
    world.spawn()  # 2

    snap = world.snapshot()

    world2 = World()
    world2.restore(snap)
    new_eid = world2.spawn()
    assert new_eid == 3


def test_empty_world_snapshot():
    """Snapshot of empty world works."""
    world = World()
    snap = world.snapshot()

    assert snap["entities"] == []
    assert snap["next_id"] == 0
    assert snap["components"] == {}

    world2 = World()
    world2.restore(snap)
    assert world2.entities() == frozenset()


def test_multi_component_entity_snapshot():
    """Entity with multiple components round-trips correctly."""
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(5.0, 6.0))
    world.attach(eid, Health(50))
    world.attach(eid, Tag(label="hero"))

    snap = world.snapshot()

    world2 = World()
    world2.register_component(Position)
    world2.register_component(Health)
    world2.register_component(Tag)
    world2.restore(snap)

    assert world2.get(eid, Position).x == 5.0
    assert world2.get(eid, Health).hp == 50
    assert world2.get(eid, Tag).label == "hero"


# --- Restore clears pre-existing state ---


def test_restore_clears_existing_state():
    """Restore replaces all world state, clearing old data."""
    world = World()
    e0 = world.spawn()
    e1 = world.spawn()
    world.attach(e0, Position(99.0, 99.0))
    world.attach(e1, Position(88.0, 88.0))

    # Create a snapshot from a different world with only one entity
    source = World()
    new_eid = source.spawn()  # entity 0
    source.attach(new_eid, Health(42))
    snap = source.snapshot()

    # Restore into the world that had two entities with Position data
    world.register_component(Health)
    world.restore(snap)

    # Entity 1 should no longer be alive (cleared by restore)
    assert not world.alive(e1)
    # Entity 0 should be alive but with Health, not Position
    assert world.alive(new_eid)
    assert world.get(new_eid, Health).hp == 42
    assert not world.has(new_eid, Position)


# --- Resumed simulation matches uninterrupted run ---


def test_resumed_simulation_matches_uninterrupted():
    """Snapshot at tick N, restore, continue — matches straight-through run."""
    results: list[float] = []

    def collector(target: list[float]):
        def sys(world: World, ctx: TickContext) -> None:
            target.append(ctx.random.random())
        return sys

    # Run A: straight through 100 ticks
    run_a: list[float] = []
    engine_a = Engine(tps=20, seed=42)
    engine_a.add_system(collector(run_a))
    engine_a.run(100)

    # Run B: 50 ticks, snapshot, restore, 50 more ticks
    run_b: list[float] = []
    engine_b = Engine(tps=20, seed=42)
    engine_b.add_system(collector(run_b))
    engine_b.run(50)
    snap = engine_b.snapshot()

    engine_c = Engine(tps=20, seed=42)
    engine_c.restore(snap)
    run_b_continued: list[float] = []
    engine_c.add_system(collector(run_b_continued))
    engine_c.run(50)

    combined = run_b + run_b_continued
    assert combined == run_a


def test_resumed_world_state_matches():
    """World entities match after snapshot/restore/continue."""

    def spawner(world: World, ctx: TickContext) -> None:
        if ctx.tick_number <= 20:
            eid = world.spawn()
            world.attach(eid, Health(hp=ctx.tick_number))

    # Run straight through
    engine_a = Engine(tps=20, seed=42)
    engine_a.add_system(spawner)
    engine_a.run(30)
    entities_a = engine_a.world.entities()

    # Run 15, snapshot, restore, run 15 more
    engine_b = Engine(tps=20, seed=42)
    engine_b.add_system(spawner)
    engine_b.run(15)
    snap = engine_b.snapshot()

    engine_c = Engine(tps=20, seed=42)
    engine_c.world.register_component(Health)
    engine_c.restore(snap)
    engine_c.add_system(spawner)
    engine_c.run(15)
    entities_c = engine_c.world.entities()

    assert entities_a == entities_c


# --- Error cases ---


def test_unregistered_component_type_raises_snapshot_error():
    """Restoring with unregistered component type raises SnapshotError."""
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))

    snap = world.snapshot()

    fresh_world = World()
    # Don't register Position
    with pytest.raises(SnapshotError, match="Unregistered component type"):
        fresh_world.restore(snap)


def test_non_dataclass_component_raises_type_error():
    """Snapshotting a world with non-dataclass component raises TypeError."""

    class PlainComponent:
        def __init__(self, value: int) -> None:
            self.value = value

    world = World()
    eid = world.spawn()
    # Bypass the dataclass check by directly inserting
    world._alive.add(999)
    world._components[PlainComponent] = {999: PlainComponent(42)}

    with pytest.raises(TypeError, match="non-dataclass"):
        world.snapshot()


def test_version_mismatch_raises_snapshot_error():
    """Restoring snapshot with wrong version raises SnapshotError."""
    engine = Engine(tps=20, seed=1)
    snap = engine.snapshot()
    snap["version"] = 999

    engine2 = Engine(tps=20, seed=1)
    with pytest.raises(SnapshotError, match="Unsupported snapshot version"):
        engine2.restore(snap)


def test_missing_version_raises_snapshot_error():
    """Restoring snapshot with missing version raises SnapshotError."""
    engine = Engine(tps=20, seed=1)
    snap = engine.snapshot()
    del snap["version"]

    engine2 = Engine(tps=20, seed=1)
    with pytest.raises(SnapshotError):
        engine2.restore(snap)


def test_tps_mismatch_raises_snapshot_error():
    """Restoring snapshot into engine with different TPS raises SnapshotError."""
    engine = Engine(tps=20, seed=1)
    snap = engine.snapshot()

    engine2 = Engine(tps=60, seed=1)
    with pytest.raises(SnapshotError, match="TPS mismatch"):
        engine2.restore(snap)


# --- Component registry ---


def test_register_component_explicit():
    """Explicitly registered components are available for restore."""
    world = World()
    world.register_component(Position)

    source = World()
    eid = source.spawn()
    source.attach(eid, Position(1.0, 2.0))
    snap = source.snapshot()

    world.restore(snap)
    assert world.get(eid, Position).x == 1.0


def test_attach_auto_registers_component():
    """Components are auto-registered when attached."""
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))

    snap = world.snapshot()

    # Restore into same world (registry intact)
    world.restore(snap)
    assert world.get(eid, Position).x == 1.0


# --- Snapshot of world with despawned entities ---


def test_snapshot_excludes_despawned_entities():
    """Snapshot only includes alive entities."""
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    world.attach(e1, Health(100))
    world.attach(e2, Health(50))
    world.despawn(e1)

    snap = world.snapshot()
    assert e1 not in snap["entities"]
    assert e2 in snap["entities"]


def test_snapshot_restore_many_entities():
    """Snapshot/restore with many entities."""
    world = World()
    for i in range(100):
        eid = world.spawn()
        world.attach(eid, Position(float(i), float(i * 2)))

    snap = world.snapshot()

    world2 = World()
    world2.register_component(Position)
    world2.restore(snap)

    assert len(world2.entities()) == 100
    pos = world2.get(50, Position)
    assert pos.x == 50.0
    assert pos.y == 100.0
