"""Tests for seed-controlled RNG determinism."""

import random
from dataclasses import dataclass

from tick.engine import Engine
from tick.world import World
from tick.types import TickContext


@dataclass
class Sample:
    value: float


# --- Seed determinism ---


def test_same_seed_produces_identical_sequences():
    """Same seed → identical random sequences across 100 ticks."""
    results_a: list[float] = []
    results_b: list[float] = []

    def collector(target: list[float]):
        def sys(world: World, ctx: TickContext) -> None:
            target.append(ctx.random.random())
        return sys

    engine_a = Engine(tps=20, seed=12345)
    engine_a.add_system(collector(results_a))
    engine_a.run(100)

    engine_b = Engine(tps=20, seed=12345)
    engine_b.add_system(collector(results_b))
    engine_b.run(100)

    assert len(results_a) == 100
    assert results_a == results_b


def test_different_seeds_produce_different_sequences():
    """Different seeds → different random sequences."""
    results_a: list[float] = []
    results_b: list[float] = []

    def collector(target: list[float]):
        def sys(world: World, ctx: TickContext) -> None:
            target.append(ctx.random.random())
        return sys

    engine_a = Engine(tps=20, seed=111)
    engine_a.add_system(collector(results_a))
    engine_a.run(50)

    engine_b = Engine(tps=20, seed=222)
    engine_b.add_system(collector(results_b))
    engine_b.run(50)

    assert results_a != results_b


def test_seed_property_returns_active_seed():
    """engine.seed is retrievable."""
    engine = Engine(tps=20, seed=42)
    assert engine.seed == 42


def test_auto_generated_seed_works():
    """Engine without explicit seed auto-generates one."""
    engine = Engine(tps=20)
    assert isinstance(engine.seed, int)
    # Should be able to run without error
    engine.add_system(lambda w, c: None)
    engine.run(10)


def test_auto_seeds_differ_between_engines():
    """Two engines without explicit seed get different seeds."""
    engine_a = Engine(tps=20)
    engine_b = Engine(tps=20)
    # Extremely unlikely to collide with 8 bytes of randomness
    assert engine_a.seed != engine_b.seed


def test_ctx_random_is_instance_of_random():
    """ctx.random is a Random instance."""
    received = []

    def sys(world: World, ctx: TickContext) -> None:
        received.append(ctx.random)

    engine = Engine(tps=20, seed=1)
    engine.add_system(sys)
    engine.step()

    assert isinstance(received[0], random.Random)


def test_systems_using_ctx_random_maintain_determinism():
    """Multiple systems using ctx.random in same tick are deterministic."""

    def sys_a(world: World, ctx: TickContext) -> None:
        for eid, (s,) in world.query(Sample):
            s.value += ctx.random.random()

    def sys_b(world: World, ctx: TickContext) -> None:
        for eid, (s,) in world.query(Sample):
            s.value += ctx.random.gauss(0, 1)

    def run_scenario(seed: int) -> float:
        engine = Engine(tps=20, seed=seed)
        eid = engine.world.spawn()
        engine.world.attach(eid, Sample(value=0.0))
        engine.add_system(sys_a)
        engine.add_system(sys_b)
        engine.run(50)
        return engine.world.get(eid, Sample).value

    val_1 = run_scenario(999)
    val_2 = run_scenario(999)
    assert val_1 == val_2


def test_rng_shared_across_systems_in_tick():
    """All systems in a tick share the same RNG instance."""
    rng_ids: list[int] = []

    def sys_a(world: World, ctx: TickContext) -> None:
        rng_ids.append(id(ctx.random))

    def sys_b(world: World, ctx: TickContext) -> None:
        rng_ids.append(id(ctx.random))

    engine = Engine(tps=20, seed=1)
    engine.add_system(sys_a)
    engine.add_system(sys_b)
    engine.step()

    assert rng_ids[0] == rng_ids[1]


def test_rng_persists_across_ticks():
    """RNG state evolves across ticks (not reset each tick)."""
    values: list[float] = []

    def sys(world: World, ctx: TickContext) -> None:
        values.append(ctx.random.random())

    engine = Engine(tps=20, seed=42)
    engine.add_system(sys)
    engine.run(5)

    # All values should be different (RNG advances)
    assert len(set(values)) == 5


def test_seed_zero_is_valid():
    """Seed of 0 should work correctly."""
    engine = Engine(tps=20, seed=0)
    assert engine.seed == 0

    values: list[float] = []

    def sys(world: World, ctx: TickContext) -> None:
        values.append(ctx.random.random())

    engine.add_system(sys)
    engine.run(5)
    assert len(values) == 5
