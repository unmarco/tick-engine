"""Orb circle renderer."""
from __future__ import annotations

import pygame

from ui.constants import EASING_COLORS, STATE_COMPLETED, STATE_WAITING


def draw_orb(
    surface: pygame.Surface,
    x: int,
    y: int,
    radius: int,
    fsm_state: str,
    easing: str,
) -> None:
    """Draw a single orb circle colored by FSM state and easing type."""
    if fsm_state == "waiting":
        fill = STATE_WAITING
    elif fsm_state == "completed":
        fill = STATE_COMPLETED
    else:
        fill = EASING_COLORS.get(easing, (200, 200, 200))

    pygame.draw.circle(surface, fill, (x, y), radius)
    # Thin outline
    outline = tuple(min(c + 40, 255) for c in fill)
    pygame.draw.circle(surface, outline, (x, y), radius, 1)
