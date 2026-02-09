"""Tests for CommandQueue."""
from __future__ import annotations

import random
from dataclasses import dataclass

import pytest
from tick import Engine, TickContext
from tick_command.queue import CommandQueue


@dataclass(frozen=True)
class PlaceStructure:
    name: str
    x: int
    y: int


@dataclass(frozen=True)
class MoveUnit:
    eid: int
    dx: int
    dy: int


def _make_ctx(engine: Engine) -> TickContext:
    """Build a TickContext from an engine (after step)."""
    return engine.clock.context(lambda: None, random.Random(42))


@pytest.fixture
def engine() -> Engine:
    return Engine(tps=20, seed=42)


@pytest.fixture
def queue() -> CommandQueue:
    return CommandQueue()


class TestQueueBasics:
    def test_empty_queue(self, queue: CommandQueue) -> None:
        assert queue.pending() == 0

    def test_enqueue_increments_pending(self, queue: CommandQueue) -> None:
        queue.enqueue(PlaceStructure("farm", 5, 3))
        assert queue.pending() == 1

    def test_enqueue_multiple(self, queue: CommandQueue) -> None:
        queue.enqueue(PlaceStructure("farm", 5, 3))
        queue.enqueue(MoveUnit(1, 0, 1))
        assert queue.pending() == 2


class TestHandlerRegistration:
    def test_register_handler(self, queue: CommandQueue) -> None:
        def handler(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            return True

        queue.handle(PlaceStructure, handler)
        # No error

    def test_overwrite_handler(self, queue: CommandQueue) -> None:
        results: list[str] = []

        def h1(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            results.append("h1")
            return True

        def h2(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            results.append("h2")
            return True

        queue.handle(PlaceStructure, h1)
        queue.handle(PlaceStructure, h2)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        engine = Engine(tps=20, seed=42)
        engine.step()
        ctx = _make_ctx(engine)
        queue.drain(engine.world, ctx)
        assert results == ["h2"]


class TestDrain:
    def test_drain_empty(self, queue: CommandQueue, engine: Engine) -> None:
        engine.step()
        ctx = _make_ctx(engine)
        results = queue.drain(engine.world, ctx)
        assert results == []

    def test_drain_calls_handler(self, queue: CommandQueue, engine: Engine) -> None:
        called: list[PlaceStructure] = []

        def handler(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            called.append(cmd)
            return True

        queue.handle(PlaceStructure, handler)
        cmd = PlaceStructure("farm", 5, 3)
        queue.enqueue(cmd)

        engine.step()
        ctx = _make_ctx(engine)
        results = queue.drain(engine.world, ctx)

        assert called == [cmd]
        assert results == [(cmd, True)]
        assert queue.pending() == 0

    def test_drain_fifo_order(self, queue: CommandQueue, engine: Engine) -> None:
        order: list[str] = []

        def handler(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            order.append(cmd.name)
            return True

        queue.handle(PlaceStructure, handler)
        queue.enqueue(PlaceStructure("first", 0, 0))
        queue.enqueue(PlaceStructure("second", 1, 1))
        queue.enqueue(PlaceStructure("third", 2, 2))

        engine.step()
        ctx = _make_ctx(engine)
        queue.drain(engine.world, ctx)
        assert order == ["first", "second", "third"]

    def test_drain_returns_reject(self, queue: CommandQueue, engine: Engine) -> None:
        def handler(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            return False

        queue.handle(PlaceStructure, handler)
        cmd = PlaceStructure("farm", 5, 3)
        queue.enqueue(cmd)

        engine.step()
        ctx = _make_ctx(engine)
        results = queue.drain(engine.world, ctx)
        assert results == [(cmd, False)]

    def test_drain_mixed_types(self, queue: CommandQueue, engine: Engine) -> None:
        def place_handler(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            return True

        def move_handler(cmd: MoveUnit, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            return False

        queue.handle(PlaceStructure, place_handler)
        queue.handle(MoveUnit, move_handler)

        p = PlaceStructure("farm", 0, 0)
        m = MoveUnit(1, 0, 1)
        queue.enqueue(p)
        queue.enqueue(m)

        engine.step()
        ctx = _make_ctx(engine)
        results = queue.drain(engine.world, ctx)
        assert results == [(p, True), (m, False)]

    def test_drain_no_handler_raises_typeerror(
        self, queue: CommandQueue, engine: Engine
    ) -> None:
        queue.enqueue(PlaceStructure("farm", 0, 0))
        engine.step()
        ctx = _make_ctx(engine)
        with pytest.raises(TypeError, match="No handler registered"):
            queue.drain(engine.world, ctx)

    def test_drain_clears_pending(self, queue: CommandQueue, engine: Engine) -> None:
        queue.handle(PlaceStructure, lambda cmd, w, c: True)
        queue.enqueue(PlaceStructure("farm", 0, 0))

        engine.step()
        ctx = _make_ctx(engine)
        queue.drain(engine.world, ctx)
        assert queue.pending() == 0

        # Second drain is empty
        results = queue.drain(engine.world, ctx)
        assert results == []


class TestDrainWithWorldMutation:
    def test_handler_can_mutate_world(self, queue: CommandQueue, engine: Engine) -> None:
        @dataclass
        class Marker:
            label: str

        engine.world.register_component(Marker)

        def handler(cmd: PlaceStructure, world, ctx) -> bool:  # type: ignore[no-untyped-def]
            eid = world.spawn()
            world.attach(eid, Marker(label=cmd.name))
            return True

        queue.handle(PlaceStructure, handler)
        queue.enqueue(PlaceStructure("farm", 5, 3))

        engine.step()
        ctx = _make_ctx(engine)
        queue.drain(engine.world, ctx)

        entities = list(engine.world.query(Marker))
        assert len(entities) == 1
        _, (marker,) = entities[0]
        assert marker.label == "farm"
