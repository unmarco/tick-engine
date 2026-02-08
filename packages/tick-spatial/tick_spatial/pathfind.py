"""A* pathfinding over any SpatialIndex."""
from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick_spatial.types import SpatialIndex


def pathfind(
    index: SpatialIndex,
    start: tuple[int, int],
    goal: tuple[int, int],
    cost: Callable[[tuple[int, int], tuple[int, int]], float] | None = None,
    walkable: Callable[[tuple[int, int]], bool] | None = None,
) -> list[tuple[int, int]] | None:
    if walkable is not None and (not walkable(start) or not walkable(goal)):
        return None

    open_set: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    counter = 1

    closed: set[tuple[int, int]] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path: list[tuple[int, int]] = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for neighbor in index.neighbors(*current):
            if walkable is not None and not walkable(neighbor):
                continue
            step_cost = cost(current, neighbor) if cost is not None else 1.0
            tentative = g_score[current] + step_cost
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                h = index.heuristic(neighbor, goal)
                heapq.heappush(open_set, (tentative + h, counter, neighbor))
                counter += 1

    return None
