"""Entity-Component-System pattern -- movement simulation.

Demonstrates:
- Defining components as plain dataclasses
- Spawning entities and attaching components
- Querying entities by component type
- Mutating component data inside a system

Run: python -m examples.ecs
"""

from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext


# ---------------------------------------------------------------------------
# Components -- plain dataclasses, data only
# ---------------------------------------------------------------------------

@dataclass
class Position:
    x: float
    y: float


@dataclass
class Velocity:
    dx: float
    dy: float


# ---------------------------------------------------------------------------
# Systems -- functions that read and mutate components
# ---------------------------------------------------------------------------

def movement_system(world: World, ctx: TickContext) -> None:
    """Move every entity that has both Position and Velocity."""
    for eid, (pos, vel) in world.query(Position, Velocity):
        pos.x += vel.dx * ctx.dt
        pos.y += vel.dy * ctx.dt


def print_positions(world: World, ctx: TickContext) -> None:
    """Print all positions at the end of each tick."""
    parts = []
    for eid, (pos,) in world.query(Position):
        parts.append(f"  e{eid}: ({pos.x:6.2f}, {pos.y:6.2f})")
    print(f"tick {ctx.tick_number}:" + "".join(parts))


# ---------------------------------------------------------------------------
# Setup and run
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== ECS: Movement ===\n")

    engine = Engine(tps=10)
    engine.add_system(movement_system)
    engine.add_system(print_positions)

    w = engine.world

    # Spawn three entities with position and velocity.
    e0 = w.spawn()
    w.attach(e0, Position(0.0, 0.0))
    w.attach(e0, Velocity(1.0, 0.0))    # moves right

    e1 = w.spawn()
    w.attach(e1, Position(10.0, 10.0))
    w.attach(e1, Velocity(0.0, -2.0))   # moves down

    e2 = w.spawn()
    w.attach(e2, Position(5.0, 5.0))
    w.attach(e2, Velocity(-0.5, 0.5))   # moves up-left

    # Run 5 ticks.
    engine.run(5)

    # Read final positions directly.
    print("\nFinal state:")
    for eid in sorted(w.entities()):
        pos = w.get(eid, Position)
        print(f"  entity {eid}: ({pos.x:.2f}, {pos.y:.2f})")


if __name__ == "__main__":
    main()
