"""HUD overlays — pause indicator, speed display."""
from __future__ import annotations

import pygame


def draw_pause_overlay(
    surface: pygame.Surface,
    font: pygame.font.Font,
    grid_px: int,
) -> None:
    """Draw a semi-transparent pause overlay over the grid."""
    overlay = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 100))
    surface.blit(overlay, (0, 0))

    big_font = pygame.font.SysFont("monospace", 32, bold=True)
    text = big_font.render("PAUSED", True, (255, 255, 255))
    tr = text.get_rect(center=(grid_px // 2, grid_px // 2))
    surface.blit(text, tr)

    hint = font.render("Space to resume", True, (180, 180, 180))
    hr = hint.get_rect(center=(grid_px // 2, grid_px // 2 + 30))
    surface.blit(hint, hr)
