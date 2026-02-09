"""Accept/reject flash overlays."""
from __future__ import annotations

import time

import pygame

from tick_command import resolve_footprint
from ui.constants import TILE_SIZE, MAP_W, MAP_H


class Flash:
    """A temporary colored outline over a footprint."""

    def __init__(
        self,
        coords: list[tuple[int, int]],
        color: tuple[int, int, int],
        duration: float,
    ) -> None:
        self.coords = coords
        self.color = color
        self.created = time.monotonic()
        self.duration = duration

    def alive(self) -> bool:
        return time.monotonic() - self.created < self.duration

    def alpha(self) -> float:
        elapsed = time.monotonic() - self.created
        return max(0.0, 1.0 - elapsed / self.duration)


class FeedbackLayer:
    """Manages flash overlays for accept/reject feedback."""

    def __init__(self) -> None:
        self._flashes: list[Flash] = []

    def flash_accept(self, origin: tuple[int, int], footprint: tuple[int, ...]) -> None:
        coords = resolve_footprint(origin, footprint)
        self._flashes.append(Flash(coords, (0, 255, 0), 0.3))

    def flash_reject(self, origin: tuple[int, int], footprint: tuple[int, ...]) -> None:
        coords = resolve_footprint(origin, footprint)
        self._flashes.append(Flash(coords, (255, 0, 0), 0.5))

    def draw(self, surface: pygame.Surface) -> None:
        alive: list[Flash] = []
        for flash in self._flashes:
            if not flash.alive():
                continue
            alive.append(flash)
            a = flash.alpha()
            r, g, b = flash.color
            color = (int(r * a), int(g * a), int(b * a))
            for cx, cy in flash.coords:
                if 0 <= cx < MAP_W and 0 <= cy < MAP_H:
                    rect = pygame.Rect(
                        cx * TILE_SIZE + 1,
                        cy * TILE_SIZE + 1,
                        TILE_SIZE - 2,
                        TILE_SIZE - 2,
                    )
                    pygame.draw.rect(surface, color, rect, 3)
        self._flashes = alive
