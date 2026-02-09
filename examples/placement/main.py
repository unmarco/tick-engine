"""Placement Playground — interactive building placement with pygame."""
from __future__ import annotations

import sys

import pygame

from tick import Engine
from tick_command import CommandQueue, make_command_system
from tick_spatial import Grid2D, Pos2D

from game.buildings import make_blueprints
from game.commands import PlaceStructure, Demolish
from game.components import Structure
from game.handlers import register_handlers
from game.mapgen import generate_island
from ui.constants import (
    SCREEN_W, SCREEN_H, GRID_W, GRID_H,
    MAP_W, MAP_H, TILE_SIZE, FPS, TPS,
)
from ui.feedback import FeedbackLayer
from ui.palette import Palette
from ui.renderer import draw_grid, draw_structures, draw_hover_preview
from ui.status import StatusBar


def check_placement_valid(
    name: str,
    mx: int,
    my: int,
    state: "GameState",
) -> bool:
    """Pre-check if a placement would succeed (for hover preview color)."""
    blueprints = state.blueprints
    if not blueprints.has(name):
        return False
    meta = blueprints.meta(name)
    from tick_command import resolve_footprint
    footprint_shape = meta.get("footprint", (1, 1))
    terrain_reqs = meta.get("terrain_reqs", {})
    stackable = meta.get("stackable", False)

    coords = resolve_footprint((mx, my), footprint_shape)
    for cx, cy in coords:
        if not (0 <= cx < state.grid.width and 0 <= cy < state.grid.height):
            return False
    if terrain_reqs:
        for coord in coords:
            if not state.cellmap.matches(coord, terrain_reqs):
                return False
    for coord in coords:
        if not state.cellmap.passable(coord):
            return False
    if not stackable:
        for coord in coords:
            entities_at = state.grid.at(coord)
            for eid in entities_at:
                if state.engine.world.has(eid, Structure):
                    occ = state.engine.world.get(eid, Structure)
                    occ_meta = blueprints.meta(occ.name)
                    if not occ_meta.get("stackable", False):
                        return False
    return True


class GameState:
    """Holds all game objects."""

    def __init__(self) -> None:
        self.engine = Engine(tps=TPS, seed=42)
        self.engine.world.register_component(Structure)
        self.engine.world.register_component(Pos2D)

        self.grid = Grid2D(width=MAP_W, height=MAP_H)
        self.cellmap = generate_island(MAP_W, MAP_H, seed=42)
        self.blueprints = make_blueprints()
        self.queue = CommandQueue()
        self.feedback = FeedbackLayer()
        self.status = StatusBar()
        self.palette = Palette(self.blueprints)
        self.demolish_mode = False

        # Wire up command handlers with feedback callbacks
        def on_place(cmd: PlaceStructure) -> None:
            meta = self.blueprints.meta(cmd.name)
            fp = meta.get("footprint", (1, 1))
            self.feedback.flash_accept((cmd.x, cmd.y), fp)
            label = meta.get("label", cmd.name)
            self.status.set(f"Placed {label} at ({cmd.x}, {cmd.y})", (100, 255, 100))

        def on_demolish(cmd: Demolish) -> None:
            self.feedback.flash_accept((cmd.x, cmd.y), (1, 1))
            self.status.set(f"Demolished at ({cmd.x}, {cmd.y})", (255, 180, 80))

        def on_reject(cmd: object) -> None:
            if isinstance(cmd, PlaceStructure):
                meta = self.blueprints.meta(cmd.name)
                fp = meta.get("footprint", (1, 1))
                self.feedback.flash_reject((cmd.x, cmd.y), fp)
                label = meta.get("label", cmd.name)
                self.status.set(f"Cannot place {label} here", (255, 80, 80))
            elif isinstance(cmd, Demolish):
                self.status.set("Nothing to demolish", (255, 80, 80))

        register_handlers(
            self.queue, self.blueprints, self.cellmap, self.grid,
            on_place=on_place, on_demolish=on_demolish, on_reject=on_reject,
        )

        # Add the command system to the engine
        self.engine.add_system(
            make_command_system(self.queue, on_reject=on_reject)
        )


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Placement Playground")
    clock = pygame.time.Clock()

    state = GameState()

    # Tick accumulator for fixed-rate engine ticks
    tick_interval = 1.0 / TPS
    accumulator = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        accumulator += dt

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_d:
                    state.demolish_mode = not state.demolish_mode
                    if state.demolish_mode:
                        state.status.set("Demolish mode ON", (255, 180, 80))
                    else:
                        state.status.set("Demolish mode OFF", (200, 200, 200))
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    idx = event.key - pygame.K_1
                    state.palette.select(idx)
                    state.demolish_mode = False
                    meta = state.blueprints.meta(state.palette.selected_name)
                    label = meta.get("label", state.palette.selected_name)
                    state.status.set(f"Selected: {label}", (200, 200, 200))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos[0] // TILE_SIZE, event.pos[1] // TILE_SIZE
                if 0 <= mx < MAP_W and 0 <= my < MAP_H:
                    if event.button == 1:  # Left click
                        if state.demolish_mode:
                            state.queue.enqueue(Demolish(x=mx, y=my))
                        else:
                            name = state.palette.selected_name
                            state.queue.enqueue(PlaceStructure(name=name, x=mx, y=my))
                    elif event.button == 3:  # Right click
                        state.queue.enqueue(Demolish(x=mx, y=my))

        # --- Tick engine at fixed rate ---
        while accumulator >= tick_interval:
            state.engine.step()
            accumulator -= tick_interval

        # --- Render ---
        screen.fill((20, 20, 30))

        # Terrain grid
        draw_grid(screen, state.cellmap)

        # Structures
        draw_structures(screen, state.engine.world, state.grid, state.blueprints)

        # Hover preview
        mouse_pos = pygame.mouse.get_pos()
        mx = mouse_pos[0] // TILE_SIZE
        my = mouse_pos[1] // TILE_SIZE
        if 0 <= mx < MAP_W and 0 <= my < MAP_H and not state.demolish_mode:
            name = state.palette.selected_name
            meta = state.blueprints.meta(name)
            fp = meta.get("footprint", (1, 1))
            valid = check_placement_valid(name, mx, my, state)
            draw_hover_preview(screen, mx, my, fp, valid)
        elif 0 <= mx < MAP_W and 0 <= my < MAP_H and state.demolish_mode:
            # Red cursor for demolish
            rect = pygame.Rect(mx * TILE_SIZE, my * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, (255, 80, 80), rect, 2)

        # Flash overlays
        state.feedback.draw(screen)

        # Sidebar
        sidebar_rect = pygame.Rect(GRID_W, 0, SCREEN_W - GRID_W, GRID_H)
        pygame.draw.rect(screen, (25, 25, 35), sidebar_rect)
        state.palette.draw(screen, state.demolish_mode)

        # Status bar
        state.status.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
