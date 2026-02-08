"""HexGrid - hexagonal grid with axial coordinates (flat-top)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tick_spatial.types import Coord, Pos2D

if TYPE_CHECKING:
    from tick import World

_HEX_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def _hex_distance(dq: int, dr: int) -> int:
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


class HexGrid:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._cells: dict[Coord, set[int]] = {}
        self._entities: dict[int, Coord] = {}

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def _check_bounds(self, coord: Coord) -> None:
        q, r = coord
        if not (0 <= q < self._width and 0 <= r < self._height):
            raise ValueError(
                f"{coord} out of bounds for {self._width}x{self._height} hex grid"
            )

    def place(self, eid: int, coord: Coord) -> None:
        self._check_bounds(coord)
        self.remove(eid)
        self._entities[eid] = coord
        if coord not in self._cells:
            self._cells[coord] = set()
        self._cells[coord].add(eid)

    def move(self, eid: int, coord: Coord) -> None:
        self._check_bounds(coord)
        if eid not in self._entities:
            raise KeyError(f"Entity {eid} is not on the grid")
        old = self._entities[eid]
        self._cells[old].discard(eid)
        if not self._cells[old]:
            del self._cells[old]
        self._entities[eid] = coord
        if coord not in self._cells:
            self._cells[coord] = set()
        self._cells[coord].add(eid)

    def remove(self, eid: int) -> None:
        pos = self._entities.pop(eid, None)
        if pos is not None:
            cell = self._cells.get(pos)
            if cell is not None:
                cell.discard(eid)
                if not cell:
                    del self._cells[pos]

    def at(self, coord: Coord) -> frozenset[int]:
        return frozenset(self._cells.get(coord, ()))

    def position_of(self, eid: int) -> Coord | None:
        return self._entities.get(eid)

    def in_radius(self, coord: Coord, r: int) -> list[tuple[int, Coord]]:
        q, rv = coord
        result: list[tuple[int, Coord]] = []
        for dq in range(-r, r + 1):
            for dr in range(-r, r + 1):
                if _hex_distance(dq, dr) > r:
                    continue
                cq, cr = q + dq, rv + dr
                if 0 <= cq < self._width and 0 <= cr < self._height:
                    for eid in self._cells.get((cq, cr), ()):
                        result.append((eid, (cq, cr)))
        return result

    def neighbors(self, coord: Coord) -> list[Coord]:
        q, r = coord
        result: list[Coord] = []
        for dq, dr in _HEX_DIRS:
            nq, nr = q + dq, r + dr
            if 0 <= nq < self._width and 0 <= nr < self._height:
                result.append((nq, nr))
        return result

    def heuristic(self, a: Coord, b: Coord) -> float:
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
                self.place(eid, (q, r))
