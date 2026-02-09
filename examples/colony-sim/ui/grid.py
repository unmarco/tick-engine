"""Grid rendering — terrain tiles, colonists, stockpile, selection."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from game.components import Colonist, SelectedTag, VisualPos
from game.terrain import FOREST, WATER
from tick_atlas import CellMap
from tick_fsm import FSM
from tick_spatial import Grid2D
from ui.constants import (
    COLOR_FOREST,
    COLOR_GRASS,
    COLOR_SELECTED_RING,
    COLOR_STOCKPILE,
    COLOR_WATER,
    STATE_COLORS,
)

if TYPE_CHECKING:
    from tick import World
    from tick_spatial import Coord


def draw_terrain(
    surface: pygame.Surface,
    cells: CellMap,
    map_size: int,
    tile_size: int,
    stockpile_coord: tuple[int, int],
) -> None:
    """Draw terrain tiles."""
    for x in range(map_size):
        for y in range(map_size):
            cell = cells.at((x, y))
            if cell.name == "water":
                color = COLOR_WATER
            elif cell.name == "forest":
                color = COLOR_FOREST
            else:
                color = COLOR_GRASS
            rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (0, 0, 0), rect, 1)

    # Stockpile marker
    sx, sy = stockpile_coord
    sr = pygame.Rect(sx * tile_size, sy * tile_size, tile_size, tile_size)
    pygame.draw.rect(surface, COLOR_STOCKPILE, sr)
    pygame.draw.rect(surface, (0, 0, 0), sr, 1)


def draw_colonists(
    surface: pygame.Surface,
    world: World,
    grid: Grid2D,
    tile_size: int,
) -> None:
    """Draw colonists as colored circles based on FSM state."""
    radius = max(3, tile_size // 3)
    for eid, (col, fsm) in world.query(Colonist, FSM):
        # Use VisualPos for smooth movement if available
        if world.has(eid, VisualPos):
            vp = world.get(eid, VisualPos)
            px = vp.prev_x + (vp.curr_x - vp.prev_x) * vp.progress
            py = vp.prev_y + (vp.curr_y - vp.prev_y) * vp.progress
            cx = int(px) + tile_size // 2
            cy = int(py) + tile_size // 2
        else:
            pos = grid.position_of(eid)
            if pos is None:
                continue
            cx = pos[0] * tile_size + tile_size // 2
            cy = pos[1] * tile_size + tile_size // 2

        color = STATE_COLORS.get(fsm.state, (180, 180, 180))
        pygame.draw.circle(surface, color, (cx, cy), radius)

        # Selection ring
        if world.has(eid, SelectedTag):
            pygame.draw.circle(surface, COLOR_SELECTED_RING, (cx, cy), radius + 2, 2)


def draw_stockpile_food(
    surface: pygame.Surface,
    food_count: int,
    stockpile_coord: tuple[int, int],
    tile_size: int,
    font: pygame.font.Font,
) -> None:
    """Draw food count on the stockpile tile."""
    sx, sy = stockpile_coord
    cx = sx * tile_size + tile_size // 2
    cy = sy * tile_size + tile_size // 2
    text = font.render(str(food_count), True, (40, 30, 10))
    tr = text.get_rect(center=(cx, cy))
    surface.blit(text, tr)


def draw_need_bars(
    surface: pygame.Surface,
    world: World,
    grid: Grid2D,
    tile_size: int,
) -> None:
    """Draw small hunger/fatigue bars below colonists."""
    from tick_colony import NeedSet, NeedHelper

    bar_w = max(8, tile_size - 4)
    bar_h = 2
    for eid, (col, ns) in world.query(Colonist, NeedSet):
        if world.has(eid, VisualPos):
            vp = world.get(eid, VisualPos)
            px = vp.prev_x + (vp.curr_x - vp.prev_x) * vp.progress
            py = vp.prev_y + (vp.curr_y - vp.prev_y) * vp.progress
            bx = int(px) + (tile_size - bar_w) // 2
            by = int(py) + tile_size - 6
        else:
            pos = grid.position_of(eid)
            if pos is None:
                continue
            bx = pos[0] * tile_size + (tile_size - bar_w) // 2
            by = pos[1] * tile_size + tile_size - 6

        # Hunger bar
        hunger = NeedHelper.get_value(ns, "hunger") / 100.0
        pygame.draw.rect(surface, (40, 40, 50), (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, (220, 80, 60), (bx, by, int(bar_w * hunger), bar_h))

        # Fatigue bar
        fatigue = NeedHelper.get_value(ns, "fatigue") / 100.0
        pygame.draw.rect(surface, (40, 40, 50), (bx, by + bar_h + 1, bar_w, bar_h))
        pygame.draw.rect(surface, (80, 140, 220), (bx, by + bar_h + 1, int(bar_w * fatigue), bar_h))
