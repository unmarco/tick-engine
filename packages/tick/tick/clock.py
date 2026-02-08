"""Clock and TickContext for fixed-timestep engine."""

import random
from typing import Callable

from tick.types import TickContext


class Clock:
    def __init__(self, tps: int) -> None:
        if tps <= 0:
            raise ValueError("tps must be positive")
        self._tps = tps
        self._dt = 1.0 / tps
        self._tick_number = 0

    @property
    def tps(self) -> int:
        return self._tps

    @property
    def dt(self) -> float:
        return self._dt

    @property
    def tick_number(self) -> int:
        return self._tick_number

    def advance(self) -> int:
        self._tick_number += 1
        return self._tick_number

    def context(self, stop_fn: Callable[[], None], rng: random.Random) -> TickContext:
        return TickContext(
            tick_number=self._tick_number,
            dt=self._dt,
            elapsed=self._tick_number * self._dt,
            request_stop=stop_fn,
            random=rng,
        )

    def reset(self, tick_number: int = 0) -> None:
        self._tick_number = tick_number
