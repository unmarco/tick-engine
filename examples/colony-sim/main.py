"""Colony-Sim — Visual chronicle with light interaction.

A visual, lightly interactive colony simulation exercising all 13 tick-engine
packages. Watch colonists autonomously forage, rest, and build while seasons
cycle and world events unfold.

Controls:
  Space       Pause / Resume
  1-4         Speed (0.5x / 1x / 2x / 4x)
  F1          Food Drop ability
  F2          Rally ability
  F3          Shelter ability
  Left-click  Select colonist (click empty to deselect)
  Right-click Move selected colonist to tile
  Escape      Quit
"""
from __future__ import annotations

import argparse
import sys

import pygame

from game.commands import MoveCommand
from game.components import Colonist, SelectedTag
from game.setup import build_game
from tick_spatial import Grid2D
from ui.constants import FPS, LOG_H, SIDEBAR_W, compute_layout
from ui.effects import draw_season_tint
from ui.grid import draw_colonists, draw_need_bars, draw_stockpile_food, draw_terrain
from ui.hud import draw_pause_overlay
from ui.log_panel import EventLogPanel
from ui.sidebar import draw_sidebar
from tick_colony import InventoryHelper, Inventory


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Colony-Sim — tick-engine visual demo")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument("--pop", type=int, default=8, help="Starting population (2-16, default: 8)")
    p.add_argument("--map-size", type=int, default=20, help="Grid width/height (12-40, default: 20)")
    p.add_argument("--tps", type=int, default=10, help="Ticks per second (default: 10)")
    p.add_argument("--chronicle", type=str, default=None,
                   metavar="FILE", help="Save JSONL chronicle to FILE on quit")
    args = p.parse_args()
    args.pop = max(2, min(16, args.pop))
    args.map_size = max(12, min(40, args.map_size))
    return args


def main() -> None:
    args = parse_args()
    layout = compute_layout(args.map_size)
    tile_size = layout["tile_size"]
    grid_px = layout["grid_px"]
    screen_w = layout["screen_w"]
    screen_h = layout["screen_h"]

    # Build game
    state = build_game(
        seed=args.seed,
        pop=args.pop,
        map_size=args.map_size,
        tps=args.tps,
        tile_size=tile_size,
    )

    # JSONL chronicle recorder (opt-in via --chronicle)
    chronicle = None
    if args.chronicle:
        from game.chronicle import ChronicleRecorder
        chronicle = ChronicleRecorder(
            state.bus, lambda: state.engine.clock.tick_number
        )

    # Event log panel
    log_panel = EventLogPanel()

    # Subscribe to signals for the event log
    def _on_birth(signal: str, data: dict) -> None:
        log_panel.add(f"{data.get('name', '?')} was born", "birth")

    def _on_death(signal: str, data: dict) -> None:
        log_panel.add(f"{data.get('name', '?')} died ({data.get('cause', '?')})", "death")

    def _on_season(signal: str, data: dict) -> None:
        log_panel.add(f"Season: {data.get('season', '?').capitalize()}", "season")

    def _on_event_start(signal: str, data: dict) -> None:
        ev = data.get("event", "?").replace("_", " ")
        log_panel.add(f"{ev.title()} began!", "event_start")

    def _on_event_end(signal: str, data: dict) -> None:
        ev = data.get("event", "?").replace("_", " ")
        log_panel.add(f"{ev.title()} ended", "event_end")

    def _on_ability(signal: str, data: dict) -> None:
        log_panel.add(data.get("text", "Ability used"), "ability")

    def _on_command(signal: str, data: dict) -> None:
        log_panel.add(data.get("text", "Command"), "command")

    def _on_exhaustion(signal: str, data: dict) -> None:
        log_panel.add(f"{data.get('name', '?')} is exhausted!", "death")

    state.bus.subscribe("birth", _on_birth)
    state.bus.subscribe("death", _on_death)
    state.bus.subscribe("season", _on_season)
    state.bus.subscribe("event_start", _on_event_start)
    state.bus.subscribe("event_end", _on_event_end)
    state.bus.subscribe("ability", _on_ability)
    state.bus.subscribe("command", _on_command)
    state.bus.subscribe("exhaustion", _on_exhaustion)

    # Pygame init
    pygame.init()
    screen = pygame.display.set_mode((screen_w, screen_h))
    pygame.display.set_caption("Colony-Sim — tick-engine demo (all 13 packages)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 12)
    small_font = pygame.font.SysFont("monospace", 10)

    tick_interval = 1.0 / args.tps
    accumulator = 0.0
    step_budget = 0.0  # fractional step accumulator for sub-1x speeds
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        if not state.paused:
            accumulator += dt

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_SPACE:
                    state.paused = not state.paused

                elif event.key == pygame.K_1:
                    state.speed = 0.5
                elif event.key == pygame.K_2:
                    state.speed = 1.0
                elif event.key == pygame.K_3:
                    state.speed = 2.0
                elif event.key == pygame.K_4:
                    state.speed = 4.0

                elif event.key == pygame.K_F1:
                    ctx = state.engine.clock.context(lambda: None, state.engine._rng)
                    state.ability_mgr.invoke("food_drop", state.engine.world, ctx)
                elif event.key == pygame.K_F2:
                    ctx = state.engine.clock.context(lambda: None, state.engine._rng)
                    state.ability_mgr.invoke("rally", state.engine.world, ctx)
                elif event.key == pygame.K_F3:
                    ctx = state.engine.clock.context(lambda: None, state.engine._rng)
                    state.ability_mgr.invoke("shelter", state.engine.world, ctx)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                gx, gy = mx // tile_size, my // tile_size

                if event.button == 1:  # Left-click: select
                    if 0 <= gx < args.map_size and 0 <= gy < args.map_size and mx < grid_px:
                        _handle_select(state, gx, gy)
                    else:
                        _deselect(state)

                elif event.button == 3:  # Right-click: move command
                    if 0 <= gx < args.map_size and 0 <= gy < args.map_size and mx < grid_px:
                        if state.selected_eid is not None:
                            state.queue.enqueue(MoveCommand(coord=(gx, gy)))

        # --- Tick engine at fixed rate with speed multiplier ---
        # step_budget accumulates fractional steps (handles sub-1x speeds)
        while accumulator >= tick_interval:
            step_budget += state.speed
            accumulator -= tick_interval
        while step_budget >= 1.0:
            state.engine.step()
            step_budget -= 1.0
        # Drain excess accumulator to prevent spiral of death
        if accumulator > tick_interval * 4:
            accumulator = tick_interval * 2

        # --- Render ---
        screen.fill((20, 20, 30))

        # Terrain
        draw_terrain(screen, state.cells, args.map_size, tile_size, state.stockpile_coord)

        # Season tint
        season = _get_season(state)
        draw_season_tint(screen, season, grid_px)

        # Colonists
        draw_colonists(screen, state.engine.world, state.grid, tile_size)

        # Need bars
        draw_need_bars(screen, state.engine.world, state.grid, tile_size)

        # Stockpile food count
        food = 0
        if state.engine.world.alive(state.stockpile_eid) and state.engine.world.has(state.stockpile_eid, Inventory):
            food = InventoryHelper.count(state.engine.world.get(state.stockpile_eid, Inventory), "food")
        draw_stockpile_food(screen, food, state.stockpile_coord, tile_size, small_font)

        # Pause overlay
        if state.paused:
            draw_pause_overlay(screen, font, grid_px)

        # Sidebar
        draw_sidebar(screen, font, state, grid_px, SIDEBAR_W)

        # Log panel
        log_panel.draw(screen, small_font, 0, grid_px, screen_w, LOG_H)

        pygame.display.flip()

    pygame.quit()

    # Write chronicle if requested
    if chronicle is not None and args.chronicle:
        n = chronicle.write(args.chronicle)
        print(f"Chronicle: {n} events written to {args.chronicle}")

    sys.exit()


def _handle_select(state, gx: int, gy: int) -> None:
    """Select a colonist at grid position, or deselect."""
    # Deselect previous
    _deselect(state)

    # Find colonist at position
    entities = state.grid.at((gx, gy))
    for eid in entities:
        if state.engine.world.has(eid, Colonist):
            state.engine.world.attach(eid, SelectedTag())
            state.selected_eid = eid
            return

    state.selected_eid = None


def _deselect(state) -> None:
    """Remove selection from any entity."""
    if state.selected_eid is not None:
        if state.engine.world.alive(state.selected_eid) and state.engine.world.has(state.selected_eid, SelectedTag):
            state.engine.world.detach(state.selected_eid, SelectedTag)
    state.selected_eid = None


def _get_season(state) -> str:
    """Get current active season."""
    for s in ("spring", "summer", "autumn", "winter"):
        if state.sched.is_active(s):
            return s
    return "spring"


if __name__ == "__main__":
    main()
