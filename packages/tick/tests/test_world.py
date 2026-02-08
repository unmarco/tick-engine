"""Tests for entity CRUD, component attach/detach, and queries."""

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


# --- Entity creation ---

def test_entity_creation():
    world = World()
    eid = world.spawn()
    assert isinstance(eid, int)
    assert world.alive(eid)


def test_entity_ids_are_unique():
    world = World()
    ids = [world.spawn() for _ in range(100)]
    assert len(set(ids)) == 100


def test_entity_ids_are_sequential():
    world = World()
    e0 = world.spawn()
    e1 = world.spawn()
    e2 = world.spawn()
    assert e1 == e0 + 1
    assert e2 == e1 + 1


def test_entities_returns_alive_set():
    world = World()
    a = world.spawn()
    b = world.spawn()
    assert world.entities() == frozenset({a, b})


# --- Entity destruction ---

def test_despawn_removes_entity():
    world = World()
    eid = world.spawn()
    world.despawn(eid)
    assert not world.alive(eid)
    assert eid not in world.entities()


def test_despawn_removes_all_components():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.attach(eid, Health(100))
    world.despawn(eid)
    assert not world.has(eid, Position)
    assert not world.has(eid, Health)


def test_despawn_nonexistent_entity_is_safe():
    world = World()
    world.despawn(999)


def test_entity_ids_never_reused():
    world = World()
    a = world.spawn()
    world.despawn(a)
    b = world.spawn()
    assert b != a


# --- Component attach ---

def test_component_attach():
    world = World()
    eid = world.spawn()
    pos = Position(1.0, 2.0)
    world.attach(eid, pos)
    assert world.has(eid, Position)
    assert world.get(eid, Position) is pos


def test_attach_multiple_component_types():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))
    world.attach(eid, Velocity(1.0, 1.0))
    world.attach(eid, Health(100))
    assert world.has(eid, Position)
    assert world.has(eid, Velocity)
    assert world.has(eid, Health)


def test_attach_replaces_existing_component():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.attach(eid, Position(3.0, 4.0))
    pos = world.get(eid, Position)
    assert pos.x == 3.0
    assert pos.y == 4.0


# --- Component detach ---

def test_component_detach():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.detach(eid, Position)
    assert not world.has(eid, Position)


def test_detach_nonexistent_component_is_safe():
    world = World()
    eid = world.spawn()
    world.detach(eid, Position)


def test_detach_leaves_other_components():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.attach(eid, Health(50))
    world.detach(eid, Position)
    assert not world.has(eid, Position)
    assert world.has(eid, Health)


# --- Component get ---

def test_get_returns_component():
    world = World()
    eid = world.spawn()
    world.attach(eid, Health(42))
    h = world.get(eid, Health)
    assert h.hp == 42


def test_get_missing_raises_key_error():
    world = World()
    eid = world.spawn()
    with pytest.raises(KeyError):
        world.get(eid, Position)


def test_get_despawned_entity_raises_key_error():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))
    world.despawn(eid)
    with pytest.raises(KeyError):
        world.get(eid, Position)


# --- Component has ---

def test_has_returns_true_when_present():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))
    assert world.has(eid, Position) is True


def test_has_returns_false_when_absent():
    world = World()
    eid = world.spawn()
    assert world.has(eid, Position) is False


# --- Queries ---

def test_query_single_component():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    world.attach(e1, Position(1.0, 2.0))
    world.attach(e2, Position(3.0, 4.0))
    results = list(world.query(Position))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e2}
    for _, (pos,) in results:
        assert isinstance(pos, Position)


def test_query_multiple_components():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()
    world.attach(e1, Position(0.0, 0.0))
    world.attach(e1, Velocity(1.0, 1.0))
    world.attach(e2, Position(5.0, 5.0))
    world.attach(e3, Velocity(2.0, 2.0))

    results = list(world.query(Position, Velocity))
    assert len(results) == 1
    eid, (pos, vel) = results[0]
    assert eid == e1
    assert isinstance(pos, Position)
    assert isinstance(vel, Velocity)


def test_query_returns_nothing_for_empty_world():
    world = World()
    results = list(world.query(Position))
    assert results == []


def test_query_no_component_types():
    world = World()
    world.spawn()
    results = list(world.query())
    assert results == []


def test_query_skips_despawned_entities():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    world.attach(e1, Position(1.0, 1.0))
    world.attach(e2, Position(2.0, 2.0))
    world.despawn(e1)
    results = list(world.query(Position))
    assert len(results) == 1
    assert results[0][0] == e2


def test_query_component_order_matches_argument_order():
    world = World()
    eid = world.spawn()
    pos = Position(1.0, 2.0)
    vel = Velocity(3.0, 4.0)
    world.attach(eid, pos)
    world.attach(eid, vel)

    results = list(world.query(Position, Velocity))
    _, (r_pos, r_vel) = results[0]
    assert r_pos is pos
    assert r_vel is vel

    results = list(world.query(Velocity, Position))
    _, (r_vel, r_pos) = results[0]
    assert r_vel is vel
    assert r_pos is pos


def test_query_is_generator():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(0.0, 0.0))
    import types
    result = world.query(Position)
    assert isinstance(result, types.GeneratorType)


def test_component_mutation_through_query():
    world = World()
    eid = world.spawn()
    world.attach(eid, Health(100))
    for _, (h,) in world.query(Health):
        h.hp -= 10
    assert world.get(eid, Health).hp == 90


# --- Alive-entity guards (v0.1.1) ---


def test_attach_to_despawned_entity_raises_dead_entity_error():
    world = World()
    eid = world.spawn()
    world.despawn(eid)
    with pytest.raises(DeadEntityError) as exc_info:
        world.attach(eid, Position(0.0, 0.0))
    assert exc_info.value.entity_id == eid


def test_attach_to_never_spawned_entity_raises_dead_entity_error():
    world = World()
    with pytest.raises(DeadEntityError) as exc_info:
        world.attach(999, Position(0.0, 0.0))
    assert exc_info.value.entity_id == 999


def test_get_despawned_entity_raises_dead_entity_error():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.despawn(eid)
    with pytest.raises(DeadEntityError) as exc_info:
        world.get(eid, Position)
    assert exc_info.value.entity_id == eid


def test_has_on_despawned_entity_returns_false():
    world = World()
    eid = world.spawn()
    world.attach(eid, Position(1.0, 2.0))
    world.despawn(eid)
    assert world.has(eid, Position) is False


def test_has_on_never_spawned_entity_returns_false():
    world = World()
    assert world.has(999, Position) is False


def test_dead_entity_error_is_key_error_subclass():
    assert issubclass(DeadEntityError, KeyError)


def test_dead_entity_error_carries_entity_id():
    err = DeadEntityError(42, "test message")
    assert err.entity_id == 42
    assert "test message" in str(err)
