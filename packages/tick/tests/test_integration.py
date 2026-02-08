"""Tests for multi-system scenarios and determinism."""

from dataclasses import dataclass

from tick.engine import Engine
from tick.world import World
from tick.types import TickContext


@dataclass
class Position:
    x: float
    y: float


@dataclass
class Velocity:
    dx: float
    dy: float


@dataclass
class Lifetime:
    remaining: int


@dataclass
class Tag:
    label: str


# --- Multi-system scenarios ---

def test_movement_system():
    engine = Engine(tps=10)
    w = engine.world
    eid = w.spawn()
    w.attach(eid, Position(0.0, 0.0))
    w.attach(eid, Velocity(1.0, 2.0))

    def move(world: World, ctx: TickContext) -> None:
        for _, (pos, vel) in world.query(Position, Velocity):
            pos.x += vel.dx * ctx.dt
            pos.y += vel.dy * ctx.dt

    engine.add_system(move)
    engine.run(10)
    pos = w.get(eid, Position)
    assert abs(pos.x - 1.0) < 1e-9
    assert abs(pos.y - 2.0) < 1e-9


def test_entity_creation_mid_simulation():
    engine = Engine(tps=20)
    w = engine.world
    spawn_counts = []

    def spawner(world: World, ctx: TickContext) -> None:
        if ctx.tick_number <= 5:
            eid = world.spawn()
            world.attach(eid, Tag(label=f"born-{ctx.tick_number}"))

    def counter(world: World, ctx: TickContext) -> None:
        count = len(list(world.query(Tag)))
        spawn_counts.append(count)

    engine.add_system(spawner)
    engine.add_system(counter)
    engine.run(10)
    # Ticks 1-5 each spawn one entity, counter sees them immediately
    assert spawn_counts[0] == 1
    assert spawn_counts[4] == 5
    assert spawn_counts[9] == 5


def test_entity_destruction_mid_simulation():
    engine = Engine(tps=20)
    w = engine.world

    entities = []
    for i in range(5):
        eid = w.spawn()
        w.attach(eid, Lifetime(remaining=i + 1))
        entities.append(eid)

    alive_counts = []

    def decay(world: World, ctx: TickContext) -> None:
        to_kill = []
        for eid, (life,) in world.query(Lifetime):
            life.remaining -= 1
            if life.remaining <= 0:
                to_kill.append(eid)
        for eid in to_kill:
            world.despawn(eid)

    def count_alive(world: World, ctx: TickContext) -> None:
        alive_counts.append(len(world.entities()))

    engine.add_system(decay)
    engine.add_system(count_alive)
    engine.run(5)
    # After tick 1: entity with remaining=1 dies -> 4 alive
    # After tick 2: entity with remaining=2 dies -> 3 alive
    # etc.
    assert alive_counts == [4, 3, 2, 1, 0]


def test_systems_mutate_state_visible_to_later_systems():
    engine = Engine(tps=20)
    w = engine.world
    eid = w.spawn()
    w.attach(eid, Position(0.0, 0.0))
    w.attach(eid, Velocity(5.0, 0.0))

    seen_positions = []

    def move(world: World, ctx: TickContext) -> None:
        for _, (pos, vel) in world.query(Position, Velocity):
            pos.x += vel.dx * ctx.dt

    def observe(world: World, ctx: TickContext) -> None:
        pos = world.get(eid, Position)
        seen_positions.append(pos.x)

    engine.add_system(move)
    engine.add_system(observe)
    engine.run(3)
    # observer should see post-move position each tick
    assert abs(seen_positions[0] - 0.25) < 1e-9
    assert abs(seen_positions[1] - 0.50) < 1e-9
    assert abs(seen_positions[2] - 0.75) < 1e-9


def test_multi_component_query():
    engine = Engine(tps=20)
    w = engine.world

    # Entity with all components
    full = w.spawn()
    w.attach(full, Position(0.0, 0.0))
    w.attach(full, Velocity(1.0, 0.0))
    w.attach(full, Tag(label="full"))

    # Entity with only Position
    partial = w.spawn()
    w.attach(partial, Position(5.0, 5.0))

    matched = []

    def system(world: World, ctx: TickContext) -> None:
        for eid, (pos, vel, tag) in world.query(Position, Velocity, Tag):
            matched.append(eid)

    engine.add_system(system)
    engine.run(1)
    assert matched == [full]


# --- Determinism ---

def run_deterministic_scenario() -> list[tuple[int, float]]:
    engine = Engine(tps=20)
    w = engine.world

    for i in range(10):
        eid = w.spawn()
        w.attach(eid, Position(float(i), 0.0))
        w.attach(eid, Velocity(float(i) * 0.5, 1.0))
        w.attach(eid, Lifetime(remaining=5 + i * 2))

    snapshots: list[tuple[int, float]] = []

    def move(world: World, ctx: TickContext) -> None:
        for _, (pos, vel) in world.query(Position, Velocity):
            pos.x += vel.dx * ctx.dt
            pos.y += vel.dy * ctx.dt

    def decay(world: World, ctx: TickContext) -> None:
        to_kill = []
        for eid, (life,) in world.query(Lifetime):
            life.remaining -= 1
            if life.remaining <= 0:
                to_kill.append(eid)
        for eid in to_kill:
            world.despawn(eid)

    def snapshot(world: World, ctx: TickContext) -> None:
        positions = sorted(
            (eid, pos.x) for eid, (pos,) in world.query(Position)
        )
        total_x = sum(x for _, x in positions)
        snapshots.append((len(positions), total_x))

    engine.add_system(move)
    engine.add_system(decay)
    engine.add_system(snapshot)
    engine.run(30)
    return snapshots


def test_determinism():
    run1 = run_deterministic_scenario()
    run2 = run_deterministic_scenario()
    assert len(run1) == len(run2)
    for (count1, total1), (count2, total2) in zip(run1, run2):
        assert count1 == count2
        assert abs(total1 - total2) < 1e-9


def test_determinism_entity_counts():
    results = run_deterministic_scenario()
    # First tick: all 10 alive
    assert results[0][0] == 10
    # Last tick should have fewer (entities with short lifetimes die)
    assert results[-1][0] < 10


# --- Stop signaling ---

def test_stop_from_system_with_condition():
    engine = Engine(tps=20)
    w = engine.world
    eid = w.spawn()
    w.attach(eid, Position(0.0, 0.0))
    w.attach(eid, Velocity(10.0, 0.0))

    def move(world: World, ctx: TickContext) -> None:
        for _, (pos, vel) in world.query(Position, Velocity):
            pos.x += vel.dx * ctx.dt

    def check_boundary(world: World, ctx: TickContext) -> None:
        pos = world.get(eid, Position)
        if pos.x >= 2.0:
            ctx.request_stop()

    engine.add_system(move)
    engine.add_system(check_boundary)
    engine.run(1000)
    pos = w.get(eid, Position)
    assert pos.x >= 2.0
    assert engine.clock.tick_number < 1000


# --- Large-scale scenario ---

def test_many_entities():
    engine = Engine(tps=20)
    w = engine.world

    for i in range(1000):
        eid = w.spawn()
        w.attach(eid, Position(float(i), 0.0))

    count = [0]

    def counter(world: World, ctx: TickContext) -> None:
        count[0] = len(list(world.query(Position)))

    engine.add_system(counter)
    engine.run(1)
    assert count[0] == 1000
