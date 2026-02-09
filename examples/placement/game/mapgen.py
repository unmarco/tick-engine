"""Procedural island terrain generation."""
from __future__ import annotations

import random

from tick_atlas import CellMap

from game.terrain import VOID, GRASS, FOREST, WATER, STONE, SAND


def generate_island(width: int, height: int, seed: int = 42) -> CellMap:
    """Generate a procedural island map.

    Layout: water border -> sand edge -> grass/forest/stone interior.
    Every cell is explicitly set() so matches() works on all coordinates.
    """
    rng = random.Random(seed)
    cellmap = CellMap(default=VOID)

    cx, cy = width / 2, height / 2
    max_dist = min(cx, cy)

    for x in range(width):
        for y in range(height):
            # Distance from center, normalized to 0..1
            dx = (x - cx) / max_dist
            dy = (y - cy) / max_dist
            dist = (dx * dx + dy * dy) ** 0.5

            if dist > 0.95:
                cellmap.set((x, y), WATER)
            elif dist > 0.80:
                # Transition zone: mostly sand, some water
                if rng.random() < (dist - 0.80) / 0.15 * 0.3:
                    cellmap.set((x, y), WATER)
                else:
                    cellmap.set((x, y), SAND)
            elif dist > 0.65:
                cellmap.set((x, y), GRASS)
            else:
                # Interior: mix of grass, forest, stone
                roll = rng.random()
                if roll < 0.15:
                    cellmap.set((x, y), STONE)
                elif roll < 0.45:
                    cellmap.set((x, y), FOREST)
                else:
                    cellmap.set((x, y), GRASS)

    return cellmap
