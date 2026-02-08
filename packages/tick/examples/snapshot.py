"""Snapshot and restore -- save, rewind, and replay.

Demonstrates:
- Taking a snapshot mid-simulation
- Restoring from a snapshot to rewind state
- Proving that restored simulations produce identical results
- JSON serialization round-trip of snapshots

Run: python -m examples.snapshot
"""

import json
from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext


@dataclass
class Counter:
    value: int


def increment_system(world: World, ctx: TickContext) -> None:
    """Increment each counter by a random amount each tick."""
    for eid, (c,) in world.query(Counter):
        c.value += ctx.random.randint(1, 10)


def read_counters(world: World) -> list[int]:
    """Return sorted counter values for comparison."""
    return sorted(c.value for _, (c,) in world.query(Counter))


def main() -> None:
    print("=== Snapshot & Restore ===\n")

    engine = Engine(tps=20, seed=42)
    engine.add_system(increment_system)

    # Spawn 3 entities with counters starting at 0.
    for _ in range(3):
        eid = engine.world.spawn()
        engine.world.attach(eid, Counter(value=0))

    # --- Phase 1: Run 10 ticks, then snapshot ---
    engine.run(10)
    snap = engine.snapshot()
    counters_at_snap = read_counters(engine.world)
    print(f"After 10 ticks (snapshot taken): {counters_at_snap}")

    # --- Phase 2: Continue 10 more ticks ---
    engine.run(10)
    result_a = read_counters(engine.world)
    print(f"After 20 ticks (continued):     {result_a}")

    # --- Phase 3: JSON round-trip ---
    snap_json = json.dumps(snap)
    snap_restored = json.loads(snap_json)
    print(f"\nSnapshot JSON size: {len(snap_json)} bytes")

    # --- Phase 4: Restore and replay ---
    engine.restore(snap_restored)
    counters_after_restore = read_counters(engine.world)
    print(f"After restore to tick 10:       {counters_after_restore}")

    engine.run(10)
    result_b = read_counters(engine.world)
    print(f"After 20 ticks (replayed):      {result_b}")

    # --- Verify ---
    print()
    assert counters_at_snap == counters_after_restore, "Restore failed!"
    print("Restore matches snapshot:  PASS")

    assert result_a == result_b, f"Replay mismatch: {result_a} != {result_b}"
    print("Replay matches original:  PASS")

    print("\nSnapshots are fully deterministic -- restore and replay produce")
    print("identical results every time.")


if __name__ == "__main__":
    main()
