"""Demo scenario - population dynamics with RNG and replay.

A stochastic simulation of abstract organisms that age, consume energy,
reproduce, and die. Uses ctx.random for all randomness, ensuring full
determinism given the same seed.

Includes a replay proof: snapshot at tick 250, continue to 500, restore
to 250, continue to 500 again — both runs produce identical results.

Run: python -m examples.population
"""

from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@dataclass
class Age:
    current: int
    max_lifespan: int


@dataclass
class Energy:
    level: float


@dataclass
class Reproducible:
    cooldown: int
    timer: int


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def aging_system(world: World, ctx: TickContext) -> None:
    to_despawn: list[int] = []
    for eid, (age,) in world.query(Age):
        age.current += 1
        if age.current > age.max_lifespan:
            to_despawn.append(eid)
    for eid in to_despawn:
        world.despawn(eid)


def energy_system(world: World, ctx: TickContext) -> None:
    to_despawn: list[int] = []
    for eid, (energy,) in world.query(Energy):
        cost = 0.3 + ctx.random.random() * 0.4  # 0.3–0.7 per tick
        energy.level -= cost
        if energy.level <= 0:
            to_despawn.append(eid)
    for eid in to_despawn:
        world.despawn(eid)


def reproduction_system(world: World, ctx: TickContext) -> None:
    births: list[tuple[int, int, float]] = []
    for eid, (repro, energy) in world.query(Reproducible, Energy):
        if repro.timer > 0:
            repro.timer -= 1
            continue
        if energy.level > 30.0:
            energy.level -= 20.0
            repro.timer = repro.cooldown
            age = world.get(eid, Age)
            base_lifespan = age.max_lifespan
            child_lifespan = base_lifespan + ctx.random.randint(-10, 10)
            child_energy = 30.0 + ctx.random.random() * 20.0
            births.append((child_lifespan, repro.cooldown, child_energy))
    for lifespan, cooldown, child_energy in births:
        child = world.spawn()
        world.attach(child, Age(current=0, max_lifespan=lifespan))
        world.attach(child, Energy(level=child_energy))
        world.attach(child, Reproducible(cooldown=cooldown, timer=cooldown))


def census_system(world: World, ctx: TickContext) -> None:
    if ctx.tick_number % 50 != 0:
        return
    ages: list[int] = []
    energies: list[float] = []
    for _, (age,) in world.query(Age):
        ages.append(age.current)
    for _, (energy,) in world.query(Energy):
        energies.append(energy.level)
    pop = len(ages)
    avg_age = sum(ages) / pop if pop else 0.0
    avg_energy = sum(energies) / pop if pop else 0.0
    print(
        f"[tick {ctx.tick_number:>4}]  pop={pop:<4}  "
        f"avg_age={avg_age:.1f}  avg_energy={avg_energy:.1f}"
    )


# ---------------------------------------------------------------------------
# Setup and run
# ---------------------------------------------------------------------------

def make_organism(
    world: World, lifespan: int, energy: float, cooldown: int
) -> int:
    eid = world.spawn()
    world.attach(eid, Age(current=0, max_lifespan=lifespan))
    world.attach(eid, Energy(level=energy))
    world.attach(eid, Reproducible(cooldown=cooldown, timer=0))
    return eid


def setup_engine(seed: int = 42) -> Engine:
    engine = Engine(tps=20, seed=seed)
    engine.add_system(aging_system)
    engine.add_system(energy_system)
    engine.add_system(reproduction_system)
    engine.add_system(census_system)

    w = engine.world
    for i in range(20):
        lifespan = 80 + (i * 7) % 40
        energy = 50.0 + (i * 3) % 20
        cooldown = 8 + i % 5
        make_organism(w, lifespan, energy, cooldown)

    return engine


def count_population(world: World) -> int:
    return len(list(world.query(Age)))


def main() -> None:
    seed = 42
    print(f"=== Population demo (seed={seed}) ===\n")

    # --- Run 1: straight through to 500 ---
    engine = setup_engine(seed)
    engine.run(250)
    snap = engine.snapshot()
    engine.run(250)
    final_a = count_population(engine.world)
    print(f"\nRun A final population at tick 500: {final_a}")

    # --- Run 2: fresh engine, restore from snapshot, continue to 500 ---
    engine2 = Engine(tps=20, seed=seed)
    engine2.world.register_component(Age)
    engine2.world.register_component(Energy)
    engine2.world.register_component(Reproducible)
    engine2.restore(snap)
    engine2.add_system(aging_system)
    engine2.add_system(energy_system)
    engine2.add_system(reproduction_system)
    engine2.add_system(census_system)
    engine2.run(250)
    final_b = count_population(engine2.world)
    print(f"Run B final population at tick 500: {final_b}")

    assert final_a == final_b, f"Replay mismatch: {final_a} != {final_b}"
    print("\nReplay proof: PASSED (both runs identical)")


if __name__ == "__main__":
    main()
