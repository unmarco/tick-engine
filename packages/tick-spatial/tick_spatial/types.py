"""Shared types and protocols for tick-spatial."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tick import World

Coord = tuple[int, ...]


@dataclass
class Pos2D:
    x: float
    y: float


@dataclass
class Pos3D:
    x: float
    y: float
    z: float


class SpatialIndex(Protocol):
    def place(self, eid: int, coord: Coord) -> None: ...
    def move(self, eid: int, coord: Coord) -> None: ...
    def remove(self, eid: int) -> None: ...
    def at(self, coord: Coord) -> frozenset[int]: ...
    def position_of(self, eid: int) -> Coord | None: ...
    def in_radius(self, coord: Coord, r: int) -> list[tuple[int, Coord]]: ...
    def neighbors(self, coord: Coord) -> list[Coord]: ...
    def heuristic(self, a: Coord, b: Coord) -> float: ...
    def tracked_entities(self) -> frozenset[int]: ...
    def rebuild(self, world: World) -> None: ...
