"""Grid and structure rendering."""
from __future__ import annotations

import pygame

from tick import World
from tick_atlas import CellMap
from tick_blueprint import BlueprintRegistry
from tick_command import resolve_footprint
from tick_spatial import Grid2D

from game.buildings import BUILDING_COLORS
from game.components import Structure
from game.terrain import TERRAIN_COLORS
from ui.constants import TILE_SIZE, MAP_W, MAP_H, GRID_W, GRID_H


def draw_grid(surface: pygame.Surface, cellmap: CellMap) -> None:
    """Draw the terrain grid."""
    for x in range(MAP_W):
        for y in range(MAP_H):
            cell = cellmap.at((x, y))
            color = TERRAIN_COLORS.get(cell.name, (40, 40, 40))
            rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(surface, color, rect)

    # Grid lines
    for x in range(MAP_W + 1):
        pygame.draw.line(surface, (30, 30, 30), (x * TILE_SIZE, 0), (x * TILE_SIZE, GRID_H))
    for y in range(MAP_H + 1):
        pygame.draw.line(surface, (30, 30, 30), (0, y * TILE_SIZE), (GRID_W, y * TILE_SIZE))


def draw_structures(
    surface: pygame.Surface,
    world: World,
    grid: Grid2D,
    blueprints: BlueprintRegistry,
) -> None:
    """Draw placed structures as colored rectangles spanning their footprint."""
    for eid in grid.tracked_entities():
        if not world.has(eid, Structure):
            continue
        struct = world.get(eid, Structure)
        pos = grid.position_of(eid)
        if pos is None:
            continue

        meta = blueprints.meta(struct.name)
        footprint_shape = meta.get("footprint", (1, 1))
        coords = resolve_footprint(pos, footprint_shape)

        color = BUILDING_COLORS.get(struct.name, (200, 200, 200))

        # Find bounding rect
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        px = min_x * TILE_SIZE + 2
        py = min_y * TILE_SIZE + 2
        pw = (max_x - min_x + 1) * TILE_SIZE - 4
        ph = (max_y - min_y + 1) * TILE_SIZE - 4

        rect = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, (255, 255, 255), rect, 1)


def draw_hover_preview(
    surface: pygame.Surface,
    mx: int,
    my: int,
    footprint_shape: tuple[int, ...],
    valid: bool,
) -> None:
    """Draw a footprint preview at the cursor position."""
    if mx < 0 or my < 0 or mx >= MAP_W or my >= MAP_H:
        return

    coords = resolve_footprint((mx, my), footprint_shape)
    color = (255, 255, 0) if valid else (255, 80, 80)

    for cx, cy in coords:
        if 0 <= cx < MAP_W and 0 <= cy < MAP_H:
            rect = pygame.Rect(cx * TILE_SIZE, cy * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(surface, color, rect, 2)
