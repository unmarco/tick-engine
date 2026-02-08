from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick import World


@dataclass
class Position:
    x: int
    y: int


class Grid:
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
            raise ValueError(f"({x}, {y}) out of bounds for {self._width}x{self._height} grid")

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
                for eid in self._cells.get((ex, ey), ()):
                    result.append((eid, ex, ey))
        return result

    def neighbors(self, x: int, y: int, diagonal: bool = True) -> list[tuple[int, int]]:
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if diagonal:
            dirs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        result: list[tuple[int, int]] = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self._width and 0 <= ny < self._height:
                result.append((nx, ny))
        return result

    def pathfind(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        passable: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[int, int]] | None:
        if passable is not None and (not passable(*start) or not passable(*goal)):
            return None
        open_set: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start)]
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start: 0.0}
        counter = 1
        while open_set:
            _, _, current = heapq.heappop(open_set)
            if current == goal:
                path: list[tuple[int, int]] = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path
            for nx, ny in self.neighbors(*current):
                if passable is not None and not passable(nx, ny):
                    continue
                tentative = g_score[current] + 1.0
                if tentative < g_score.get((nx, ny), float("inf")):
                    came_from[(nx, ny)] = current
                    g_score[(nx, ny)] = tentative
                    h = max(abs(nx - goal[0]), abs(ny - goal[1]))
                    heapq.heappush(open_set, (tentative + h, counter, (nx, ny)))
                    counter += 1
        return None

    def rebuild(self, world: World) -> None:
        self._cells.clear()
        self._entities.clear()
        for eid, (pos,) in world.query(Position):
            self.place(eid, pos.x, pos.y)


def make_grid_cleanup_system(grid: Grid) -> Callable:
    def grid_cleanup_system(world: World, ctx: object) -> None:
        dead = [eid for eid in grid._entities if not world.alive(eid)]
        for eid in dead:
            grid.remove(eid)
    return grid_cleanup_system
