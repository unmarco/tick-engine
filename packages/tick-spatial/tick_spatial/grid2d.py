"""Grid2D - 2D integer grid with Chebyshev distance."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tick_spatial.types import Pos2D

if TYPE_CHECKING:
    from tick import World


class Grid2D:
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

    def _check_bounds(self, x: int, y: int) -> None:
        if not (0 <= x < self._width and 0 <= y < self._height):
            raise ValueError(
                f"({x}, {y}) out of bounds for {self._width}x{self._height} grid"
            )

    def place(self, eid: int, x: int, y: int) -> None:
        self._check_bounds(x, y)
        self.remove(eid)
        pos = (x, y)
        self._entities[eid] = pos
        if pos not in self._cells:
            self._cells[pos] = set()
        self._cells[pos].add(eid)

    def move(self, eid: int, x: int, y: int) -> None:
        self._check_bounds(x, y)
        if eid not in self._entities:
            raise KeyError(f"Entity {eid} is not on the grid")
        old = self._entities[eid]
        self._cells[old].discard(eid)
        if not self._cells[old]:
            del self._cells[old]
        pos = (x, y)
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

    def at(self, x: int, y: int) -> frozenset[int]:
        return frozenset(self._cells.get((x, y), ()))

    def position_of(self, eid: int) -> tuple[int, int] | None:
        return self._entities.get(eid)

    def in_radius(self, x: int, y: int, r: int) -> list[tuple[int, int, int]]:
        result: list[tuple[int, int, int]] = []
        for ex in range(max(0, x - r), min(self._width, x + r + 1)):
            for ey in range(max(0, y - r), min(self._height, y + r + 1)):
                if max(abs(ex - x), abs(ey - y)) <= r:
                    for eid in self._cells.get((ex, ey), ()):
                        result.append((eid, ex, ey))
        return result

    def neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        dirs = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]
        result: list[tuple[int, int]] = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self._width and 0 <= ny < self._height:
                result.append((nx, ny))
        return result

    def heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        return float(max(abs(a[0] - b[0]), abs(a[1] - b[1])))

    def tracked_entities(self) -> frozenset[int]:
        return frozenset(self._entities)

    def rebuild(self, world: World) -> None:
        self._cells.clear()
        self._entities.clear()
        for eid, (pos,) in world.query(Pos2D):
            x, y = int(pos.x), int(pos.y)
            if 0 <= x < self._width and 0 <= y < self._height:
                self.place(eid, x, y)
