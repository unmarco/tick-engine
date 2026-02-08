"""Hello World -- the simplest possible tick engine program.

Demonstrates:
- Creating an engine with a fixed tick rate
- Defining a system as a plain function
- Registering a system and running the loop
- Accessing tick_number, dt, and elapsed from TickContext

Run: python -m examples.basics
"""

from tick import Engine, World
from tick.types import TickContext


# A system is just a function that takes (world, ctx).
def hello_system(world: World, ctx: TickContext) -> None:
    print(
        f"  tick {ctx.tick_number}  |  dt={ctx.dt:.3f}s  |  elapsed={ctx.elapsed:.3f}s"
    )


def main() -> None:
    print("=== Hello World ===\n")

    # Create an engine running at 10 ticks per second.
    engine = Engine(tps=10)

    # Register our system. It will be called once per tick.
    engine.add_system(hello_system)

    # Run exactly 5 ticks, then stop.
    engine.run(5)

    print(f"\nDone. Clock stopped at tick {engine.clock.tick_number}.")


if __name__ == "__main__":
    main()
