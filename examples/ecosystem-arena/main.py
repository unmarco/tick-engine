"""
Ecosystem Arena — tick-ai + tick-physics Pygame Demo

Predator-prey simulation where predators use behavior trees and prey use
utility AI. Physics handles all movement and collisions.
"""
from __future__ import annotations

import sys

import pygame

from tick_ai.components import Blackboard
from tick_physics import KinematicBody

from game.components import Species, Visual
from game.setup import (
    HEIGHT,
    WIDTH,
    FPS,
    TPS,
    PRED_START_ENERGY,
    GameState,
    build_game,
    _spawn_predator,
    _spawn_prey,
)

TITLE = "Ecosystem Arena — tick-ai + tick-physics"
BG_COLOR = (18, 22, 30)
HUD_COLOR = (200, 200, 220)
ENERGY_BAR_W = 20
ENERGY_BAR_H = 3


def _draw_entities(screen: pygame.Surface, state: GameState) -> tuple[int, int]:
    """Draw all entities and return (predator_count, prey_count)."""
    w = state.engine.world
    pred_count = 0
    prey_count = 0

    for eid, (body, vis, sp) in w.query(KinematicBody, Visual, Species):
        x, y = int(body.position[0]), int(body.position[1])
        r = vis.radius

        if sp.kind == "predator":
            pred_count += 1
            # Color darkens as energy drops
            energy = 100.0
            if w.has(eid, Blackboard):
                energy = max(0.0, w.get(eid, Blackboard).data.get("energy", 0.0))
            frac = min(energy / PRED_START_ENERGY, 1.0)
            cr = int(vis.color[0] * frac)
            cg = int(vis.color[1] * frac)
            cb = int(vis.color[2] * frac)
            pygame.draw.circle(screen, (cr, cg, cb), (x, y), r)
            pygame.draw.circle(screen, (180, 30, 30), (x, y), r, 1)

            # Energy bar above
            bar_x = x - ENERGY_BAR_W // 2
            bar_y = y - r - 6
            pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, ENERGY_BAR_W, ENERGY_BAR_H))
            fill_w = int(ENERGY_BAR_W * frac)
            bar_color = (50, 200, 50) if frac > 0.4 else (200, 200, 50) if frac > 0.2 else (200, 50, 50)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, ENERGY_BAR_H))

        elif sp.kind == "prey":
            prey_count += 1
            pygame.draw.circle(screen, vis.color, (x, y), r)
            pygame.draw.circle(screen, (120, 230, 140), (x, y), r, 1)

    return pred_count, prey_count


def _draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    state: GameState,
    pred_count: int,
    prey_count: int,
    fps_val: float,
) -> None:
    """Draw HUD overlay."""
    tick_num = state.engine.clock.tick_number
    pause_str = "  [PAUSED]" if state.paused else ""

    lines = [
        f"Predators: {pred_count}   Prey: {prey_count}   "
        f"Tick: {tick_num}   FPS: {fps_val:.0f}{pause_str}",
        "Space=Pause  P=Predator  E=Prey  C=Clear  R=Reset  Esc=Quit",
    ]
    for i, line in enumerate(lines):
        surf = font.render(line, True, HUD_COLOR)
        screen.blit(surf, (10, 8 + i * 20))


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    pg_clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 14)

    state = build_game()

    tick_acc = 0.0
    tick_interval = 1.0 / TPS
    running = True

    while running:
        dt = pg_clock.tick(FPS) / 1000.0

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    state.paused = not state.paused
                elif event.key == pygame.K_p:
                    mx, my = pygame.mouse.get_pos()
                    _spawn_predator(state.engine, state.manager, float(mx), float(my))
                elif event.key == pygame.K_e:
                    mx, my = pygame.mouse.get_pos()
                    _spawn_prey(state.engine, state.manager, float(mx), float(my))
                elif event.key == pygame.K_c:
                    # Clear all entities
                    eids = [eid for eid, _ in state.engine.world.query(Species)]
                    for eid in eids:
                        state.engine.world.despawn(eid)
                elif event.key == pygame.K_r:
                    state = build_game()
                    tick_acc = 0.0

        # --- Update (tick accumulator) ---
        if not state.paused:
            tick_acc += dt
            while tick_acc >= tick_interval:
                state.engine.step()
                tick_acc -= tick_interval

        # --- Draw ---
        screen.fill(BG_COLOR)
        pred_count, prey_count = _draw_entities(screen, state)
        _draw_hud(screen, font, state, pred_count, prey_count, pg_clock.get_fps())
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
