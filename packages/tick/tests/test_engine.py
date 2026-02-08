"""Tests for engine lifecycle, tick counting, and pacing."""

import time
from dataclasses import dataclass
from unittest.mock import patch

from tick.engine import Engine
from tick.world import World
from tick.types import TickContext


@dataclass
class Counter:
    value: int


# --- Initialization ---

def test_engine_init_defaults():
    engine = Engine()
    assert engine.clock.tps == 20
    assert engine.clock.tick_number == 0
    assert isinstance(engine.world, World)


def test_engine_init_custom_tps():
    engine = Engine(tps=60)
    assert engine.clock.tps == 60


# --- System registration ---

def test_add_system():
    engine = Engine()
    calls = []

    def sys(world, ctx):
        calls.append(ctx.tick_number)

    engine.add_system(sys)
    engine.step()
    assert calls == [1]


def test_systems_run_in_order():
    engine = Engine()
    order = []

    def first(world, ctx):
        order.append("first")

    def second(world, ctx):
        order.append("second")

    def third(world, ctx):
        order.append("third")

    engine.add_system(first)
    engine.add_system(second)
    engine.add_system(third)
    engine.step()
    assert order == ["first", "second", "third"]


# --- step() ---

def test_step_advances_one_tick():
    engine = Engine()
    engine.add_system(lambda w, c: None)
    engine.step()
    assert engine.clock.tick_number == 1
    engine.step()
    assert engine.clock.tick_number == 2


def test_step_does_not_call_hooks():
    engine = Engine()
    hooks_called = []

    engine.on_start(lambda w, c: hooks_called.append("start"))
    engine.on_stop(lambda w, c: hooks_called.append("stop"))
    engine.step()
    assert hooks_called == []


# --- run(n) ---

def test_run_n_ticks():
    engine = Engine()
    tick_numbers = []

    def track(world, ctx):
        tick_numbers.append(ctx.tick_number)

    engine.add_system(track)
    engine.run(5)
    assert tick_numbers == [1, 2, 3, 4, 5]
    assert engine.clock.tick_number == 5


def test_run_calls_start_and_stop_hooks():
    engine = Engine()
    events = []

    engine.on_start(lambda w, c: events.append("start"))
    engine.on_stop(lambda w, c: events.append("stop"))
    engine.add_system(lambda w, c: events.append(f"tick-{c.tick_number}"))
    engine.run(2)
    assert events == ["start", "tick-1", "tick-2", "stop"]


def test_run_start_hook_receives_tick_zero_context():
    engine = Engine()
    start_ctx = []

    engine.on_start(lambda w, c: start_ctx.append(c.tick_number))
    engine.run(1)
    assert start_ctx == [0]


def test_run_stop_hook_receives_final_context():
    engine = Engine()
    stop_ctx = []

    engine.on_stop(lambda w, c: stop_ctx.append(c.tick_number))
    engine.run(5)
    assert stop_ctx == [5]


def test_run_zero_ticks():
    engine = Engine()
    events = []

    engine.on_start(lambda w, c: events.append("start"))
    engine.on_stop(lambda w, c: events.append("stop"))
    engine.run(0)
    assert events == ["start", "stop"]


# --- request_stop ---

def test_request_stop_from_system():
    engine = Engine()
    tick_numbers = []

    def stop_at_3(world, ctx):
        tick_numbers.append(ctx.tick_number)
        if ctx.tick_number == 3:
            ctx.request_stop()

    engine.add_system(stop_at_3)
    engine.run(100)
    assert tick_numbers == [1, 2, 3]


def test_request_stop_prevents_later_systems_in_same_tick():
    engine = Engine()
    calls = []

    def stopper(world, ctx):
        calls.append("stopper")
        ctx.request_stop()

    def after(world, ctx):
        calls.append("after")

    engine.add_system(stopper)
    engine.add_system(after)
    engine.run(1)
    assert "after" not in calls


def test_request_stop_still_calls_on_stop():
    engine = Engine()
    events = []

    def stopper(world, ctx):
        if ctx.tick_number == 1:
            ctx.request_stop()

    engine.add_system(stopper)
    engine.on_stop(lambda w, c: events.append("stop"))
    engine.run(100)
    assert events == ["stop"]


# --- run_forever ---

def test_run_forever_stops_on_request():
    engine = Engine(tps=1000)
    tick_nums = []

    def sys(world, ctx):
        tick_nums.append(ctx.tick_number)
        if ctx.tick_number >= 5:
            ctx.request_stop()

    engine.add_system(sys)
    engine.run_forever()
    assert tick_nums == [1, 2, 3, 4, 5]


def test_run_forever_calls_hooks():
    engine = Engine(tps=1000)
    events = []

    engine.on_start(lambda w, c: events.append("start"))
    engine.on_stop(lambda w, c: events.append("stop"))

    def sys(world, ctx):
        events.append(f"tick-{ctx.tick_number}")
        if ctx.tick_number >= 2:
            ctx.request_stop()

    engine.add_system(sys)
    engine.run_forever()
    assert events == ["start", "tick-1", "tick-2", "stop"]


def test_run_forever_pacing():
    engine = Engine(tps=100)  # 10ms per tick
    start_time = time.monotonic()
    count = [0]

    def sys(world, ctx):
        count[0] += 1
        if count[0] >= 5:
            ctx.request_stop()

    engine.add_system(sys)
    engine.run_forever()
    elapsed = time.monotonic() - start_time
    # 5 ticks at 100 TPS should take roughly 0.04-0.05s minimum
    # Allow generous bounds for CI/slow machines
    assert elapsed >= 0.03


# --- Lifecycle hooks ---

def test_multiple_start_hooks():
    engine = Engine()
    events = []

    engine.on_start(lambda w, c: events.append("start-1"))
    engine.on_start(lambda w, c: events.append("start-2"))
    engine.run(1)
    assert events[:2] == ["start-1", "start-2"]


def test_multiple_stop_hooks():
    engine = Engine()
    events = []

    engine.on_stop(lambda w, c: events.append("stop-1"))
    engine.on_stop(lambda w, c: events.append("stop-2"))
    engine.run(1)
    assert events[-2:] == ["stop-1", "stop-2"]


def test_hooks_receive_world():
    engine = Engine()
    eid = engine.world.spawn()
    engine.world.attach(eid, Counter(value=0))
    received_worlds = []

    def start_hook(w, c):
        received_worlds.append(w)

    engine.on_start(start_hook)
    engine.run(1)
    assert received_worlds[0] is engine.world


# --- Engine state ---

def test_world_property():
    engine = Engine()
    assert isinstance(engine.world, World)


def test_clock_property():
    engine = Engine(tps=30)
    assert engine.clock.tps == 30


def test_systems_see_each_others_changes():
    engine = Engine()
    eid = engine.world.spawn()
    engine.world.attach(eid, Counter(value=0))

    def incrementer(world, ctx):
        c = world.get(eid, Counter)
        c.value += 1

    def reader(world, ctx):
        c = world.get(eid, Counter)
        assert c.value == ctx.tick_number

    engine.add_system(incrementer)
    engine.add_system(reader)
    engine.run(5)
