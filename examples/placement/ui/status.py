"""Bottom status bar."""
from __future__ import annotations

import pygame

from ui.constants import SCREEN_W, GRID_H, STATUS_H


class StatusBar:
    """Displays messages at the bottom of the screen."""

    def __init__(self) -> None:
        self._message = ""
        self._color = (200, 200, 200)
        self._font: pygame.font.Font | None = None

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 14)
        return self._font

    def set(self, message: str, color: tuple[int, int, int] = (200, 200, 200)) -> None:
        self._message = message
        self._color = color

    def draw(self, surface: pygame.Surface) -> None:
        bar_rect = pygame.Rect(0, GRID_H, SCREEN_W, STATUS_H)
        pygame.draw.rect(surface, (30, 30, 40), bar_rect)

        if self._message:
            font = self._get_font()
            text = font.render(self._message, True, self._color)
            surface.blit(text, (8, GRID_H + 8))
