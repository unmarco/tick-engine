"""Terrain generation using tick-atlas CellDefs."""
from __future__ import annotations

import random as _random_mod

from tick_atlas import CellDef, CellMap

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=2.0, properties={"food": True})
WATER = CellDef(name="water", passable=False)

STOCKPILE_COORD_DEFAULT = (10, 10)


def generate_terrain(
    map_size: int, seed: int
) -> tuple[CellMap, tuple[int, int]]:
    """Generate terrain and return (cellmap, stockpile_coord)."""
    rng = _random_mod.Random(seed)
    cells = CellMap(default=GRASS)

    # Forest ring near edges
    for x in range(map_size):
        for y in range(map_size):
            edge_dist = min(x, y, map_size - 1 - x, map_size - 1 - y)
            if edge_dist <= 2 and rng.random() < 0.4:
                cells.set((x, y), FOREST)

    # Water feature
    wx = min(14, map_size - 4)
    wy = min(3, map_size - 5)
    cells.fill_rect((wx, wy), (min(wx + 3, map_size - 1), min(wy + 3, map_size - 1)), WATER)

    # Stockpile at center
    center = map_size // 2
    stockpile_coord = (center, center)
    cells.set(stockpile_coord, GRASS)

    return cells, stockpile_coord
