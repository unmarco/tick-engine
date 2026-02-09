"""Season tint overlays and visual effects."""
from __future__ import annotations

import pygame

from ui.constants import SEASON_TINTS


def draw_season_tint(
    surface: pygame.Surface,
    season: str,
    grid_px: int,
) -> None:
    """Draw a semi-transparent season tint over the grid area."""
    tint = SEASON_TINTS.get(season)
    if tint is None:
        return
    r, g, b, a = tint
    overlay = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
    overlay.fill((r, g, b, a))
    surface.blit(overlay, (0, 0))
