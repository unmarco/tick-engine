"""Deterministic randomness -- same seed, same results.

Demonstrates:
- Using ctx.random for stochastic behavior
- Proving determinism: same seed produces identical output
- Proving divergence: different seed produces different output

Run: python -m examples.randomness
"""

from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext


@dataclass
class Wanderer:
    x: float
    y: float


def wander_system(world: World, ctx: TickContext) -> None:
    """Move each wanderer by a random offset each tick."""
    for eid, (w,) in world.query(Wanderer):
        w.x += ctx.random.uniform(-1.0, 1.0)
        w.y += ctx.random.uniform(-1.0, 1.0)


def run_simulation(seed: int, ticks: int = 10) -> list[tuple[float, float]]:
    """Run a wanderer simulation and return final positions."""
    engine = Engine(tps=20, seed=seed)
    engine.add_system(wander_system)

    # Spawn 3 wanderers at the origin.
    for _ in range(3):
        eid = engine.world.spawn()
        engine.world.attach(eid, Wanderer(x=0.0, y=0.0))

    engine.run(ticks)

    # Collect final positions.
    results = []
    for eid, (w,) in engine.world.query(Wanderer):
        results.append((round(w.x, 6), round(w.y, 6)))
    return results


def print_positions(label: str, positions: list[tuple[float, float]]) -> None:
    print(f"  {label}:")
    for i, (x, y) in enumerate(positions):
        print(f"    wanderer {i}: ({x:+8.4f}, {y:+8.4f})")


def main() -> None:
    print("=== Deterministic Randomness ===\n")

    # Run 1: seed=42
    run_a = run_simulation(seed=42)
    print_positions("Run A (seed=42)", run_a)

    # Run 2: same seed -- should be identical
    run_b = run_simulation(seed=42)
    print_positions("Run B (seed=42)", run_b)

    print()
    if run_a == run_b:
        print("  Same seed -> IDENTICAL results (deterministic)")
    else:
        print("  ERROR: results differ despite same seed!")

    # Run 3: different seed -- should diverge
    print()
    run_c = run_simulation(seed=99)
    print_positions("Run C (seed=99)", run_c)

    print()
    if run_a != run_c:
        print("  Different seed -> DIFFERENT results (as expected)")
    else:
        print("  WARNING: different seeds produced identical results (unlikely)")


if __name__ == "__main__":
    main()
