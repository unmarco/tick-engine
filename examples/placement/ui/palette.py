"""Sidebar building selector."""
from __future__ import annotations

import pygame

from tick_blueprint import BlueprintRegistry

from game.buildings import BUILDING_NAMES, BUILDING_COLORS
from ui.constants import GRID_W, TILE_SIZE


class Palette:
    """Sidebar showing available buildings and current selection."""

    def __init__(self, blueprints: BlueprintRegistry) -> None:
        self._blueprints = blueprints
        self._names = BUILDING_NAMES
        self.selected: int = 0
        self._font: pygame.font.Font | None = None

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 14)
        return self._font

    @property
    def selected_name(self) -> str:
        return self._names[self.selected]

    def select(self, index: int) -> None:
        if 0 <= index < len(self._names):
            self.selected = index

    def draw(self, surface: pygame.Surface, demolish_mode: bool) -> None:
        font = self._get_font()
        x0 = GRID_W + 8
        y0 = 8

        # Title
        title = font.render("Buildings", True, (255, 255, 255))
        surface.blit(title, (x0, y0))
        y0 += 24

        for i, name in enumerate(self._names):
            meta = self._blueprints.meta(name)
            label = meta.get("label", name)
            key = meta.get("key", str(i + 1))
            color = BUILDING_COLORS.get(name, (200, 200, 200))

            # Selection highlight
            if i == self.selected and not demolish_mode:
                pygame.draw.rect(surface, (60, 60, 80),
                                 pygame.Rect(x0 - 4, y0 - 2, 148, 22))

            # Color swatch
            swatch = pygame.Rect(x0, y0, 14, 14)
            pygame.draw.rect(surface, color, swatch)
            pygame.draw.rect(surface, (200, 200, 200), swatch, 1)

            # Label
            text = font.render(f"[{key}] {label}", True, (220, 220, 220))
            surface.blit(text, (x0 + 20, y0 - 1))
            y0 += 24

        # Demolish mode indicator
        y0 += 12
        if demolish_mode:
            dm_text = font.render("[D] DEMOLISH", True, (255, 80, 80))
        else:
            dm_text = font.render("[D] Demolish", True, (150, 150, 150))
        surface.blit(dm_text, (x0, y0))

        # Controls
        y0 += 36
        controls = [
            "Left: Place",
            "Right: Demolish",
            "Esc: Quit",
        ]
        for line in controls:
            ct = font.render(line, True, (120, 120, 120))
            surface.blit(ct, (x0, y0))
            y0 += 18
