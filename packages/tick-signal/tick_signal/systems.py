"""System factories for signal dispatch."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_signal.bus import SignalBus

if TYPE_CHECKING:
    from tick import TickContext, World


def make_signal_system(bus: SignalBus) -> Callable[[World, TickContext], None]:
    def signal_system(world: World, ctx: TickContext) -> None:
        bus.flush()

    return signal_system
