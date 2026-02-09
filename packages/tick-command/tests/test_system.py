"""Tests for make_command_system."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from tick import Engine
from tick_command import CommandQueue, make_command_system


@dataclass(frozen=True)
class PlaceStructure:
    name: str
    x: int
    y: int


@dataclass(frozen=True)
class Demolish:
    x: int
    y: int


@pytest.fixture
def engine() -> Engine:
    return Engine(tps=20, seed=42)


class TestMakeCommandSystem:
    def test_system_drains_queue(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: True)

        system = make_command_system(queue)
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 5, 3))
        engine.step()
        assert queue.pending() == 0

    def test_on_accept_callback(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: True)

        accepted: list[Any] = []
        system = make_command_system(queue, on_accept=accepted.append)
        engine.add_system(system)

        cmd = PlaceStructure("farm", 5, 3)
        queue.enqueue(cmd)
        engine.step()
        assert accepted == [cmd]

    def test_on_reject_callback(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: False)

        rejected: list[Any] = []
        system = make_command_system(queue, on_reject=rejected.append)
        engine.add_system(system)

        cmd = PlaceStructure("farm", 5, 3)
        queue.enqueue(cmd)
        engine.step()
        assert rejected == [cmd]

    def test_accept_does_not_fire_reject(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: True)

        rejected: list[Any] = []
        accepted: list[Any] = []
        system = make_command_system(
            queue, on_accept=accepted.append, on_reject=rejected.append
        )
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        engine.step()
        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_reject_does_not_fire_accept(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: False)

        accepted: list[Any] = []
        rejected: list[Any] = []
        system = make_command_system(
            queue, on_accept=accepted.append, on_reject=rejected.append
        )
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        engine.step()
        assert len(accepted) == 0
        assert len(rejected) == 1

    def test_no_hooks_still_works(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: True)

        system = make_command_system(queue)
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        engine.step()  # Should not raise
        assert queue.pending() == 0

    def test_multiple_ticks(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: True)

        accepted: list[Any] = []
        system = make_command_system(queue, on_accept=accepted.append)
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        engine.step()
        queue.enqueue(PlaceStructure("mine", 1, 1))
        engine.step()

        assert len(accepted) == 2
        assert accepted[0].name == "farm"
        assert accepted[1].name == "mine"

    def test_multiple_command_types(self, engine: Engine) -> None:
        queue = CommandQueue()
        queue.handle(PlaceStructure, lambda cmd, w, c: True)
        queue.handle(Demolish, lambda cmd, w, c: False)

        accepted: list[Any] = []
        rejected: list[Any] = []
        system = make_command_system(
            queue, on_accept=accepted.append, on_reject=rejected.append
        )
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        queue.enqueue(Demolish(0, 0))
        engine.step()

        assert len(accepted) == 1
        assert len(rejected) == 1
        assert isinstance(accepted[0], PlaceStructure)
        assert isinstance(rejected[0], Demolish)

    def test_no_handler_raises_in_system(self, engine: Engine) -> None:
        queue = CommandQueue()
        system = make_command_system(queue)
        engine.add_system(system)

        queue.enqueue(PlaceStructure("farm", 0, 0))
        with pytest.raises(TypeError, match="No handler registered"):
            engine.step()
