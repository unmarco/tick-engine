"""Tests for query filter sentinels (Not, AnyOf)."""

from dataclasses import dataclass

import pytest

from tick.filters import AnyOf, Not
from tick.world import World


@dataclass
class Pos:
    x: float
    y: float


@dataclass
class Vel:
    dx: float
    dy: float


@dataclass
class Health:
    hp: int


@dataclass
class Dead:
    pass


@dataclass
class Frozen:
    pass


@dataclass
class Weapon:
    name: str


@dataclass
class Armor:
    defense: int


@dataclass
class Shield:
    durability: int


# --- Not filter basics ---


def test_not_excludes_entities_with_component():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e2, Pos(2.0, 2.0))
    world.attach(e3, Pos(3.0, 3.0))

    world.attach(e2, Dead())  # Mark e2 as dead

    results = list(world.query(Pos, Not(Dead)))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e3}


def test_not_returns_entities_that_lack_component():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e2, Pos(2.0, 2.0))
    world.attach(e2, Dead())

    # e1 lacks Dead, e2 has it
    results = list(world.query(Pos, Not(Dead)))
    assert len(results) == 1
    eid, (pos,) = results[0]
    assert eid == e1
    assert pos.x == 1.0


def test_not_multiple_filters_compose_as_and_not():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()
    e4 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e2, Pos(2.0, 2.0))
    world.attach(e3, Pos(3.0, 3.0))
    world.attach(e4, Pos(4.0, 4.0))

    world.attach(e2, Dead())
    world.attach(e3, Frozen())
    world.attach(e4, Dead())
    world.attach(e4, Frozen())

    # Exclude entities with Dead OR Frozen
    results = list(world.query(Pos, Not(Dead), Not(Frozen)))
    assert len(results) == 1
    assert results[0][0] == e1


def test_not_alone_iterates_all_alive_entities():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e2, Dead())
    world.attach(e3, Pos(3.0, 3.0))

    # Query with only Not filter — should iterate all alive, yield empty tuple
    results = list(world.query(Not(Dead)))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e3}

    # Check that returned tuple is empty (no plain type args)
    for _, components in results:
        assert components == ()


def test_not_for_nonexistent_component_type():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e2, Pos(2.0, 2.0))

    # No entity has Dead, so Not(Dead) has no filtering effect
    results = list(world.query(Pos, Not(Dead)))
    assert len(results) == 2


# --- AnyOf filter basics ---


def test_anyof_matches_entities_with_either_component():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()
    e4 = world.spawn()

    world.attach(e1, Weapon("sword"))
    world.attach(e2, Armor(10))
    world.attach(e3, Weapon("axe"))
    world.attach(e3, Armor(5))
    # e4 has neither

    results = list(world.query(AnyOf(Weapon, Armor)))
    assert len(results) == 3
    ids = {eid for eid, _ in results}
    assert ids == {e1, e2, e3}


def test_anyof_skips_entities_with_neither():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Weapon("dagger"))
    world.attach(e2, Pos(0.0, 0.0))  # Has neither Weapon nor Armor

    results = list(world.query(AnyOf(Weapon, Armor)))
    assert len(results) == 1
    assert results[0][0] == e1


def test_anyof_entity_with_both_matches():
    world = World()
    e1 = world.spawn()

    world.attach(e1, Weapon("lance"))
    world.attach(e1, Armor(20))

    results = list(world.query(AnyOf(Weapon, Armor)))
    assert len(results) == 1
    assert results[0][0] == e1


def test_anyof_multiple_groups_compose_as_and():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e1, Weapon("bow"))
    world.attach(e1, Shield(100))

    world.attach(e2, Armor(15))
    world.attach(e2, Shield(50))

    world.attach(e3, Weapon("staff"))
    world.attach(e3, Armor(5))
    # e3 has no Shield

    # Must have (Weapon OR Armor) AND Shield
    results = list(world.query(AnyOf(Weapon, Armor), AnyOf(Shield)))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e2}


def test_anyof_zero_args_raises_value_error():
    with pytest.raises(ValueError, match="at least one component type"):
        AnyOf()


def test_anyof_where_no_store_exists():
    world = World()
    e1 = world.spawn()

    world.attach(e1, Pos(0.0, 0.0))

    # Query for AnyOf where neither component type has a store
    results = list(world.query(AnyOf(Weapon, Armor)))
    assert results == []


# --- Composition: Not + AnyOf + plain types ---


def test_composition_plain_anyof_not():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()
    e4 = world.spawn()

    world.attach(e1, Health(100))
    world.attach(e1, Weapon("sword"))

    world.attach(e2, Health(50))
    world.attach(e2, Armor(10))

    world.attach(e3, Health(75))
    world.attach(e3, Weapon("axe"))
    world.attach(e3, Dead())

    world.attach(e4, Health(200))
    # e4 has neither Weapon nor Armor

    # Query: Health + (Weapon OR Armor) + Not Dead
    results = list(world.query(Health, AnyOf(Weapon, Armor), Not(Dead)))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e2}

    # Check that returned tuples contain only Health (the plain type arg)
    for _, (hp,) in results:
        assert isinstance(hp, Health)


def test_composition_only_plain_types_in_returned_tuple():
    world = World()
    e1 = world.spawn()

    world.attach(e1, Pos(1.0, 2.0))
    world.attach(e1, Vel(3.0, 4.0))
    world.attach(e1, Weapon("spear"))

    # Plain types: Pos, Vel
    # Filters: AnyOf(Weapon), Not(Dead)
    results = list(world.query(Pos, Vel, AnyOf(Weapon), Not(Dead)))
    assert len(results) == 1
    eid, (pos, vel) = results[0]
    assert eid == e1
    assert isinstance(pos, Pos)
    assert isinstance(vel, Vel)
    assert pos.x == 1.0
    assert vel.dx == 3.0


def test_composition_component_order_matches_plain_arg_order():
    world = World()
    e1 = world.spawn()

    pos = Pos(5.0, 6.0)
    vel = Vel(7.0, 8.0)
    health = Health(150)

    world.attach(e1, pos)
    world.attach(e1, vel)
    world.attach(e1, health)
    world.attach(e1, Weapon("hammer"))

    # Plain args in order: Health, Pos, Vel
    results = list(world.query(Health, Pos, Vel, AnyOf(Weapon), Not(Dead)))
    _, (r_health, r_pos, r_vel) = results[0]
    assert r_health is health
    assert r_pos is pos
    assert r_vel is vel


def test_composition_multiple_not_and_anyof():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e1, Weapon("sword"))

    world.attach(e2, Pos(2.0, 2.0))
    world.attach(e2, Armor(5))
    world.attach(e2, Dead())

    world.attach(e3, Pos(3.0, 3.0))
    world.attach(e3, Shield(50))
    world.attach(e3, Frozen())

    # Query: Pos + (Weapon OR Armor OR Shield) + Not Dead + Not Frozen
    results = list(world.query(
        Pos,
        AnyOf(Weapon, Armor, Shield),
        Not(Dead),
        Not(Frozen)
    ))
    assert len(results) == 1
    eid, (pos,) = results[0]
    assert eid == e1
    assert pos.x == 1.0


# --- Backward compatibility ---


def test_backward_compat_query_plain_types_unchanged():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Pos(1.0, 2.0))
    world.attach(e1, Vel(3.0, 4.0))

    world.attach(e2, Pos(5.0, 6.0))

    # Legacy query with just plain types
    results = list(world.query(Pos, Vel))
    assert len(results) == 1
    eid, (pos, vel) = results[0]
    assert eid == e1
    assert isinstance(pos, Pos)
    assert isinstance(vel, Vel)


def test_backward_compat_query_no_args_returns_nothing():
    world = World()
    world.spawn()
    world.spawn()

    results = list(world.query())
    assert results == []


def test_backward_compat_query_single_type():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Health(100))
    world.attach(e2, Health(50))

    results = list(world.query(Health))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e2}


# --- Edge cases ---


def test_edge_case_not_for_type_no_entity_has():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Pos(0.0, 0.0))
    world.attach(e2, Pos(1.0, 1.0))

    # No entity has Frozen, so Not(Frozen) should not filter anything
    results = list(world.query(Pos, Not(Frozen)))
    assert len(results) == 2


def test_edge_case_anyof_where_no_component_store_exists():
    world = World()
    e1 = world.spawn()

    world.attach(e1, Pos(0.0, 0.0))

    # Query AnyOf for types with no store
    results = list(world.query(AnyOf(Weapon, Armor, Shield)))
    assert results == []


def test_edge_case_despawned_entities_filtered_out():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e1, Weapon("sword"))

    world.attach(e2, Pos(2.0, 2.0))
    world.attach(e2, Armor(10))

    world.despawn(e1)

    results = list(world.query(Pos, AnyOf(Weapon, Armor)))
    assert len(results) == 1
    assert results[0][0] == e2


def test_edge_case_only_not_filters_yields_empty_tuples():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e2, Dead())
    world.attach(e3, Frozen())

    # Only Not filters — iterates all alive, but yields empty tuple
    results = list(world.query(Not(Dead), Not(Frozen)))
    assert len(results) == 1
    eid, components = results[0]
    assert eid == e1
    assert components == ()


def test_edge_case_anyof_single_type():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Weapon("dagger"))

    # AnyOf with single type still works
    results = list(world.query(AnyOf(Weapon)))
    assert len(results) == 1
    assert results[0][0] == e1


def test_edge_case_not_with_anyof_base():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e1, Weapon("sword"))
    world.attach(e2, Armor(10))
    world.attach(e2, Dead())
    world.attach(e3, Shield(20))

    # AnyOf as base (no plain types), then Not filter
    results = list(world.query(AnyOf(Weapon, Armor, Shield), Not(Dead)))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e3}


def test_edge_case_complex_composition_all_filters():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()
    e4 = world.spawn()

    # e1: Pos, Health, Weapon — alive
    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e1, Health(100))
    world.attach(e1, Weapon("sword"))

    # e2: Pos, Health, Armor, Dead — filtered by Not(Dead)
    world.attach(e2, Pos(2.0, 2.0))
    world.attach(e2, Health(50))
    world.attach(e2, Armor(5))
    world.attach(e2, Dead())

    # e3: Pos, Health, Shield, Frozen — filtered by Not(Frozen)
    world.attach(e3, Pos(3.0, 3.0))
    world.attach(e3, Health(75))
    world.attach(e3, Shield(30))
    world.attach(e3, Frozen())

    # e4: Pos, Health — filtered by AnyOf (has no equipment)
    world.attach(e4, Pos(4.0, 4.0))
    world.attach(e4, Health(200))

    # Query: Pos, Health + (Weapon OR Armor OR Shield) + Not Dead + Not Frozen
    results = list(world.query(
        Pos,
        Health,
        AnyOf(Weapon, Armor, Shield),
        Not(Dead),
        Not(Frozen)
    ))

    assert len(results) == 1
    eid, (pos, health) = results[0]
    assert eid == e1
    assert pos.x == 1.0
    assert health.hp == 100


# --- Query iteration base selection ---


def test_query_base_uses_required_type_if_present():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    # Create many entities with Weapon, fewer with Pos
    for i in range(10):
        eid = world.spawn()
        world.attach(eid, Weapon(f"weapon_{i}"))

    world.attach(e1, Pos(1.0, 1.0))
    world.attach(e1, Weapon("special"))

    # Query should iterate based on Pos store (smaller)
    results = list(world.query(Pos, AnyOf(Weapon)))
    assert len(results) == 1
    assert results[0][0] == e1


def test_query_base_uses_anyof_when_no_required():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()

    world.attach(e1, Weapon("sword"))
    world.attach(e2, Armor(10))

    # No plain types — base is union of first AnyOf group
    results = list(world.query(AnyOf(Weapon, Armor), Not(Dead)))
    assert len(results) == 2


def test_query_base_uses_alive_set_when_only_not():
    world = World()
    e1 = world.spawn()
    e2 = world.spawn()
    e3 = world.spawn()

    world.attach(e2, Dead())

    # No plain types, no AnyOf — iterates all alive
    results = list(world.query(Not(Dead)))
    assert len(results) == 2
    ids = {eid for eid, _ in results}
    assert ids == {e1, e3}


# --- Filter sentinel types ---


def test_not_stores_component_type():
    not_filter = Not(Dead)
    assert not_filter.ctype is Dead


def test_anyof_stores_component_types():
    anyof_filter = AnyOf(Weapon, Armor, Shield)
    assert anyof_filter.ctypes == (Weapon, Armor, Shield)


def test_anyof_validates_nonempty():
    with pytest.raises(ValueError):
        AnyOf()
