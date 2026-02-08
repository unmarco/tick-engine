"""Entity lifecycle and engine hooks -- birth, death, and shutdown.

Demonstrates:
- on_start / on_stop lifecycle hooks
- Entities with a Lifetime component that counts down
- Despawning entities when their lifetime expires
- Spawning new entities mid-simulation
- Using ctx.request_stop() to end the simulation early

Run: python -m examples.lifecycle
"""

from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@dataclass
class Lifetime:
    remaining: int


@dataclass
class Name:
    value: str


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def aging_system(world: World, ctx: TickContext) -> None:
    """Decrement lifetime; despawn entities that reach zero."""
    to_remove: list[int] = []
    for eid, (life, name) in world.query(Lifetime, Name):
        life.remaining -= 1
        if life.remaining <= 0:
            print(f"  [tick {ctx.tick_number}] {name.value} expired (despawned)")
            to_remove.append(eid)
    for eid in to_remove:
        world.despawn(eid)


def spawner_system(world: World, ctx: TickContext) -> None:
    """Spawn a new entity on tick 3."""
    if ctx.tick_number == 3:
        eid = world.spawn()
        world.attach(eid, Name(value="Charlie"))
        world.attach(eid, Lifetime(remaining=4))
        print(f"  [tick {ctx.tick_number}] Charlie spawned mid-simulation")


def stop_when_empty(world: World, ctx: TickContext) -> None:
    """Request stop when no entities remain."""
    alive_count = sum(1 for _ in world.query(Lifetime))
    if alive_count == 0:
        print(f"  [tick {ctx.tick_number}] No entities left -- requesting stop")
        ctx.request_stop()


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def on_start(world: World, ctx: TickContext) -> None:
    count = sum(1 for _ in world.query(Lifetime))
    print(f"  [start] Simulation begins with {count} entities\n")


def on_stop(world: World, ctx: TickContext) -> None:
    count = sum(1 for _ in world.query(Lifetime))
    print(f"\n  [stop] Simulation ended at tick {ctx.tick_number} with {count} entities")


# ---------------------------------------------------------------------------
# Setup and run
# ---------------------------------------------------------------------------

def spawn_entity(world: World, name: str, lifetime: int) -> int:
    eid = world.spawn()
    world.attach(eid, Name(value=name))
    world.attach(eid, Lifetime(remaining=lifetime))
    return eid


def main() -> None:
    print("=== Lifecycle: Birth, Death, Hooks ===\n")

    engine = Engine(tps=10)

    # Register hooks.
    engine.on_start(on_start)
    engine.on_stop(on_stop)

    # Register systems (order matters).
    engine.add_system(aging_system)
    engine.add_system(spawner_system)
    engine.add_system(stop_when_empty)

    # Seed with initial entities.
    spawn_entity(engine.world, "Alice", 2)    # dies on tick 2
    spawn_entity(engine.world, "Bob", 5)      # dies on tick 5

    # Run up to 20 ticks -- but request_stop will end it earlier.
    engine.run(20)


if __name__ == "__main__":
    main()
