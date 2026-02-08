"""Engine - core loop, pacing, and lifecycle hooks."""

import os
import random
import time
from typing import Any, Callable

from tick.clock import Clock
from tick.types import SnapshotError, System, TickContext
from tick.world import World

_SNAPSHOT_VERSION = 1


class Engine:
    def __init__(self, tps: int = 20, seed: int | None = None) -> None:
        self._clock = Clock(tps)
        self._world = World()
        self._systems: list[System] = []
        self._start_hooks: list[Callable[[World, TickContext], None]] = []
        self._stop_hooks: list[Callable[[World, TickContext], None]] = []
        self._stop_requested: bool = False

        if seed is None:
            seed = int.from_bytes(os.urandom(8))
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def world(self) -> World:
        return self._world

    @property
    def clock(self) -> Clock:
        return self._clock

    @property
    def seed(self) -> int:
        return self._seed

    def add_system(self, system: System) -> None:
        self._systems.append(system)

    def on_start(self, hook: Callable[[World, TickContext], None]) -> None:
        self._start_hooks.append(hook)

    def on_stop(self, hook: Callable[[World, TickContext], None]) -> None:
        self._stop_hooks.append(hook)

    def _request_stop(self) -> None:
        self._stop_requested = True

    def _tick(self) -> None:
        self._clock.advance()
        ctx = self._clock.context(self._request_stop, self._rng)
        for system in self._systems:
            system(self._world, ctx)
            if self._stop_requested:
                break

    def step(self) -> None:
        self._stop_requested = False
        self._tick()

    def run(self, n: int) -> None:
        self._stop_requested = False
        ctx = self._clock.context(self._request_stop, self._rng)
        for hook in self._start_hooks:
            hook(self._world, ctx)

        for _ in range(n):
            self._tick()
            if self._stop_requested:
                break

        ctx = self._clock.context(self._request_stop, self._rng)
        for hook in self._stop_hooks:
            hook(self._world, ctx)

    def run_forever(self) -> None:
        self._stop_requested = False
        ctx = self._clock.context(self._request_stop, self._rng)
        for hook in self._start_hooks:
            hook(self._world, ctx)

        dt = self._clock.dt
        while not self._stop_requested:
            start = time.monotonic()
            self._tick()
            if self._stop_requested:
                break
            elapsed = time.monotonic() - start
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        ctx = self._clock.context(self._request_stop, self._rng)
        for hook in self._stop_hooks:
            hook(self._world, ctx)

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": _SNAPSHOT_VERSION,
            "tick_number": self._clock.tick_number,
            "tps": self._clock.tps,
            "seed": self._seed,
            "rng_state": _serialize_rng_state(self._rng.getstate()),
            "world": self._world.snapshot(),
        }

    def restore(self, data: dict[str, Any]) -> None:
        version = data.get("version")
        if version != _SNAPSHOT_VERSION:
            raise SnapshotError(
                f"Unsupported snapshot version {version!r}, expected {_SNAPSHOT_VERSION}"
            )

        snap_tps = data.get("tps")
        if snap_tps != self._clock.tps:
            raise SnapshotError(
                f"TPS mismatch: snapshot has {snap_tps}, engine has {self._clock.tps}"
            )

        self._clock.reset(data["tick_number"])
        self._seed = data["seed"]
        self._rng.setstate(_deserialize_rng_state(data["rng_state"]))
        self._world.restore(data["world"])


def _serialize_rng_state(state: tuple[int, tuple[int, ...], float | None]) -> list[Any]:
    """Convert Random.getstate() tuple to JSON-compatible list.

    The state format (version, internalstate, gauss_next) is the
    CPython Mersenne Twister representation. Stable across CPython
    versions but may differ on other implementations (PyPy, etc.).
    """
    version, internalstate, gauss_next = state
    return [version, list(internalstate), gauss_next]


def _deserialize_rng_state(data: list[Any]) -> tuple[int, tuple[int, ...], float | None]:
    """Convert JSON list back to Random.setstate() tuple."""
    version, internalstate, gauss_next = data
    return (version, tuple(internalstate), gauss_next)
