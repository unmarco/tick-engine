"""HexGrid - hexagonal grid with axial coordinates (flat-top)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tick_spatial.types import Pos2D

if TYPE_CHECKING:
    from tick import World

_HEX_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def _hex_distance(dq: int, dr: int) -> int:
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


class HexGrid:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._cells: dict[tuple[int, int], set[int]] = {}
        self._entities: dict[int, tuple[int, int]] = {}

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def _check_bounds(self, q: int, r: int) -> None:
        if not (0 <= q < self._width and 0 <= r < self._height):
            raise ValueError(
                f"({q}, {r}) out of bounds for {self._width}x{self._height} hex grid"
            )

    def place(self, eid: int, q: int, r: int) -> None:
        self._check_bounds(q, r)
        self.remove(eid)
        pos = (q, r)
        self._entities[eid] = pos
        if pos not in self._cells:
            self._cells[pos] = set()
        self._cells[pos].add(eid)

    def move(self, eid: int, q: int, r: int) -> None:
        self._check_bounds(q, r)
        if eid not in self._entities:
            raise KeyError(f"Entity {eid} is not on the grid")
        old = self._entities[eid]
        self._cells[old].discard(eid)
        if not self._cells[old]:
            del self._cells[old]
        pos = (q, r)
        self._entities[eid] = pos
        if pos not in self._cells:
            self._cells[pos] = set()
        self._cells[pos].add(eid)

    def remove(self, eid: int) -> None:
        pos = self._entities.pop(eid, None)
        if pos is not None:
            cell = self._cells.get(pos)
            if cell is not None:
                cell.discard(eid)
                if not cell:
                    del self._cells[pos]

    def at(self, q: int, r: int) -> frozenset[int]:
        return frozenset(self._cells.get((q, r), ()))

    def position_of(self, eid: int) -> tuple[int, int] | None:
        return self._entities.get(eid)

    def in_radius(self, q: int, r: int, radius: int) -> list[tuple[int, int, int]]:
        result: list[tuple[int, int, int]] = []
        for dq in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                if _hex_distance(dq, dr) > radius:
                    continue
                cq, cr = q + dq, r + dr
                if 0 <= cq < self._width and 0 <= cr < self._height:
                    for eid in self._cells.get((cq, cr), ()):
                        result.append((eid, cq, cr))
        return result

    def neighbors(self, q: int, r: int) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for dq, dr in _HEX_DIRS:
            nq, nr = q + dq, r + dr
            if 0 <= nq < self._width and 0 <= nr < self._height:
                result.append((nq, nr))
        return result

    def heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        dq = a[0] - b[0]
        dr = a[1] - b[1]
        return float(_hex_distance(dq, dr))

    def tracked_entities(self) -> frozenset[int]:
        return frozenset(self._entities)

    def rebuild(self, world: World) -> None:
        self._cells.clear()
        self._entities.clear()
        for eid, (pos,) in world.query(Pos2D):
            q, r = int(pos.x), int(pos.y)
            if 0 <= q < self._width and 0 <= r < self._height:
                self.place(eid, q, r)
