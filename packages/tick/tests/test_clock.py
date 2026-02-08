"""Tests for clock advancement and TickContext generation."""

import random

import pytest
from tick.clock import Clock
from tick.types import TickContext

_test_rng = random.Random(0)


def test_clock_initialization():
    """Test clock initializes with correct TPS and dt."""
    clock = Clock(tps=20)
    assert clock.tps == 20
    assert clock.tick_number == 0
    # dt should be 1.0 / tps
    assert abs(clock.dt - 0.05) < 1e-9


def test_clock_initialization_custom_tps():
    """Test clock with different TPS values."""
    clock = Clock(tps=60)
    assert clock.tps == 60
    assert abs(clock.dt - (1.0 / 60)) < 1e-9

    clock = Clock(tps=10)
    assert clock.tps == 10
    assert abs(clock.dt - 0.1) < 1e-9


def test_advance_increments_tick_number():
    """Test clock advance() increments tick_number correctly."""
    clock = Clock(tps=20)
    assert clock.tick_number == 0

    result = clock.advance()
    assert result == 1
    assert clock.tick_number == 1

    result = clock.advance()
    assert result == 2
    assert clock.tick_number == 2


def test_advance_returns_new_tick_number():
    """Test advance() returns the new tick number."""
    clock = Clock(tps=20)
    assert clock.advance() == 1
    assert clock.advance() == 2
    assert clock.advance() == 3


def test_first_tick_is_one():
    """Test first tick is 1, not 0 (per spec section 5)."""
    clock = Clock(tps=20)
    assert clock.tick_number == 0  # Clock starts at 0
    clock.advance()
    assert clock.tick_number == 1  # First tick is 1


def test_multiple_advances_monotonic():
    """Test multiple advances produce monotonically increasing tick numbers."""
    clock = Clock(tps=20)
    prev = 0
    for _ in range(100):
        current = clock.advance()
        assert current == prev + 1
        prev = current


def test_context_returns_correct_values():
    """Test context() returns TickContext with correct values."""
    clock = Clock(tps=20)
    clock.advance()  # Tick 1

    stop_called = []
    def stop_fn():
        stop_called.append(True)

    rng = random.Random(0)
    ctx = clock.context(stop_fn, rng)

    assert isinstance(ctx, TickContext)
    assert ctx.tick_number == 1
    assert abs(ctx.dt - 0.05) < 1e-9
    assert abs(ctx.elapsed - 0.05) < 1e-9
    assert callable(ctx.request_stop)
    assert ctx.random is rng

    # Verify request_stop works
    ctx.request_stop()
    assert stop_called == [True]


def test_context_elapsed_calculation():
    """Test elapsed is calculated as tick_number * dt."""
    clock = Clock(tps=20)
    dt = 0.05

    for i in range(1, 11):
        clock.advance()
        ctx = clock.context(lambda: None, _test_rng)
        expected_elapsed = i * dt
        assert abs(ctx.elapsed - expected_elapsed) < 1e-9


def test_context_with_different_tps():
    """Test context elapsed with different TPS values."""
    clock = Clock(tps=60)
    dt = 1.0 / 60

    clock.advance()  # Tick 1
    ctx = clock.context(lambda: None, _test_rng)
    assert abs(ctx.elapsed - dt) < 1e-9

    clock.advance()  # Tick 2
    ctx = clock.context(lambda: None, _test_rng)
    assert abs(ctx.elapsed - 2 * dt) < 1e-9


def test_reset_resets_to_zero():
    """Test reset() sets tick back to 0."""
    clock = Clock(tps=20)

    # Advance several ticks
    for _ in range(10):
        clock.advance()
    assert clock.tick_number == 10

    # Reset
    clock.reset()
    assert clock.tick_number == 0


def test_reset_preserves_tps():
    """Test reset() preserves TPS and dt."""
    clock = Clock(tps=30)
    original_tps = clock.tps
    original_dt = clock.dt

    clock.advance()
    clock.advance()
    clock.reset()

    assert clock.tps == original_tps
    assert clock.dt == original_dt


def test_reset_and_advance_again():
    """Test clock can advance again after reset."""
    clock = Clock(tps=20)

    clock.advance()
    clock.advance()
    clock.reset()

    assert clock.tick_number == 0
    clock.advance()
    assert clock.tick_number == 1


def test_context_before_first_advance():
    """Test context at tick 0 (before first advance)."""
    clock = Clock(tps=20)
    ctx = clock.context(lambda: None, _test_rng)

    assert ctx.tick_number == 0
    assert ctx.dt == 0.05
    assert ctx.elapsed == 0.0


def test_clock_properties_are_readonly():
    """Test clock properties can be read."""
    clock = Clock(tps=25)

    # Should be able to read properties
    assert clock.tick_number == 0
    assert clock.tps == 25
    assert abs(clock.dt - 0.04) < 1e-9


def test_context_dataclass_fields():
    """Test TickContext is a frozen dataclass with correct field access."""
    clock = Clock(tps=20)
    clock.advance()

    rng = random.Random(0)
    ctx = clock.context(lambda: None, rng)

    # Access by name
    assert ctx.tick_number == 1
    assert ctx.dt == 0.05
    assert ctx.elapsed == 0.05
    assert callable(ctx.request_stop)
    assert ctx.random is rng

    # Frozen — cannot mutate
    with pytest.raises(AttributeError):
        ctx.tick_number = 99  # type: ignore[misc]


def test_elapsed_precision_over_many_ticks():
    """Test elapsed time calculation maintains precision over many ticks."""
    clock = Clock(tps=20)

    # Advance 1000 ticks
    for _ in range(1000):
        clock.advance()

    ctx = clock.context(lambda: None, _test_rng)
    expected_elapsed = 1000 * 0.05  # 50 seconds
    assert abs(ctx.elapsed - expected_elapsed) < 1e-6
