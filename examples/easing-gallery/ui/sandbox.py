"""Sandbox mode renderer."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from tick_fsm import FSM

from game.components import OrbState
from ui.constants import (
    EASING_COLORS,
    ORB_RADIUS,
    SCREEN_H,
    SCREEN_W,
    SIDEBAR_W,
    STATUS_H,
    TEXT_DIM,
)
from ui.orbs import draw_orb

if TYPE_CHECKING:
    from tick import World


def draw_sandbox(
    surface: pygame.Surface, world: World, font: pygame.font.Font
) -> None:
    """Draw sandbox mode: open field with freely placed orbs."""
    play_w = SCREEN_W - SIDEBAR_W
    play_h = SCREEN_H - STATUS_H

    # Field background
    pygame.draw.rect(surface, (18, 18, 28), (0, 0, play_w, play_h))

    # Grid dots for visual reference
    for gx in range(40, play_w, 40):
        for gy in range(40, play_h, 40):
            surface.set_at((gx, gy), (40, 40, 55))

    # Draw orbs
    for _eid, (orb, fsm) in world.query(OrbState, FSM):
        if orb.lane != -1:
            continue

        ox = int(orb.start_x + (orb.end_x - orb.start_x) * orb.progress)
        oy = int(orb.start_y + (orb.end_y - orb.start_y) * orb.progress)

        # Faint trail line
        color = EASING_COLORS.get(orb.easing, (200, 200, 200))
        dim = tuple(c // 5 for c in color)
        pygame.draw.line(
            surface, dim, (int(orb.start_x), int(orb.start_y)), (int(orb.end_x), int(orb.end_y)), 1
        )

        draw_orb(surface, ox, oy, ORB_RADIUS, fsm.state, orb.easing)

    # Mode label
    label = font.render("SANDBOX", True, TEXT_DIM)
    surface.blit(label, (play_w // 2 - label.get_width() // 2, 8))
