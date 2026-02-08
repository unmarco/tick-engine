"""Grid3D - 3D integer grid with Chebyshev distance."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tick_spatial.types import Coord, Pos3D

if TYPE_CHECKING:
    from tick import World

# 26 directions: all (dx, dy, dz) where at least one is nonzero, each in {-1, 0, 1}
_DIRS_3D = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
]


class Grid3D:
    def __init__(self, width: int, height: int, depth: int) -> None:
        self._width = width
        self._height = height
        self._depth = depth
        self._cells: dict[Coord, set[int]] = {}
        self._entities: dict[int, Coord] = {}

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def depth(self) -> int:
        return self._depth

    def _check_bounds(self, coord: Coord) -> None:
        x, y, z = coord
        if not (0 <= x < self._width and 0 <= y < self._height and 0 <= z < self._depth):
            raise ValueError(
                f"{coord} out of bounds for "
                f"{self._width}x{self._height}x{self._depth} grid"
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
        x, y, z = coord
        result: list[tuple[int, Coord]] = []
        for ex in range(max(0, x - r), min(self._width, x + r + 1)):
            for ey in range(max(0, y - r), min(self._height, y + r + 1)):
                for ez in range(max(0, z - r), min(self._depth, z + r + 1)):
                    if max(abs(ex - x), abs(ey - y), abs(ez - z)) <= r:
                        for eid in self._cells.get((ex, ey, ez), ()):
                            result.append((eid, (ex, ey, ez)))
        return result

    def neighbors(self, coord: Coord) -> list[Coord]:
        x, y, z = coord
        result: list[Coord] = []
        for dx, dy, dz in _DIRS_3D:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < self._width and 0 <= ny < self._height and 0 <= nz < self._depth:
                result.append((nx, ny, nz))
        return result

    def heuristic(self, a: Coord, b: Coord) -> float:
        return float(max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])))

    def tracked_entities(self) -> frozenset[int]:
        return frozenset(self._entities)

    def rebuild(self, world: World) -> None:
        self._cells.clear()
        self._entities.clear()
        for eid, (pos,) in world.query(Pos3D):
            x, y, z = int(pos.x), int(pos.y), int(pos.z)
            if 0 <= x < self._width and 0 <= y < self._height and 0 <= z < self._depth:
                self.place(eid, (x, y, z))
