"""Scrolling event log panel at the bottom of the screen."""
from __future__ import annotations

from collections import deque

import pygame

from ui.constants import COLOR_LOG_BG, COLOR_TEXT_DIM, LOG_COLORS


class EventLogPanel:
    """Manages a scrolling list of colored log messages."""

    def __init__(self, max_entries: int = 100) -> None:
        self.entries: deque[tuple[str, tuple[int, int, int]]] = deque(maxlen=max_entries)

    def add(self, text: str, category: str = "default") -> None:
        color = LOG_COLORS.get(category, LOG_COLORS["default"])
        self.entries.append((text, color))

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        x: int, y: int, w: int, h: int,
    ) -> None:
        """Draw the log panel."""
        # Background
        pygame.draw.rect(surface, COLOR_LOG_BG, (x, y, w, h))
        pygame.draw.line(surface, (50, 50, 60), (x, y), (x + w, y))

        # Show most recent entries that fit
        line_h = 14
        max_lines = max(1, (h - 8) // line_h)
        entries = list(self.entries)[-max_lines:]

        ty = y + 4
        for text, color in entries:
            rendered = font.render(text, True, color)
            surface.blit(rendered, (x + 6, ty))
            ty += line_h
