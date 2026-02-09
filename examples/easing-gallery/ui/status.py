"""Info panel (sidebar) and bottom status bar."""
from __future__ import annotations

import pygame

from ui.constants import (
    EASING_COLORS,
    EASING_NAMES,
    LABEL_COLOR,
    LANE_H,
    LANE_COUNT,
    SCREEN_W,
    SIDEBAR_W,
    STATUS_BG,
    STATUS_H,
    SIDEBAR_BG,
    TEXT_COLOR,
    TEXT_DIM,
)


def draw_sidebar(
    surface: pygame.Surface,
    font: pygame.font.Font,
    wave_count: int,
    complete_count: int,
    duration: int,
    tps: int,
    auto_wave: bool,
    mode: str,
    selected_easing: str,
) -> None:
    """Draw right-side info panel."""
    x = SCREEN_W - SIDEBAR_W
    h = LANE_H * LANE_COUNT

    # Background
    pygame.draw.rect(surface, SIDEBAR_BG, (x, 0, SIDEBAR_W, h))
    pygame.draw.line(surface, (50, 50, 70), (x, 0), (x, h))

    pad = 10
    line_h = 22
    cx = x + pad
    cy = 8

    # Title
    title = font.render("INFO", True, LABEL_COLOR)
    surface.blit(title, (cx, cy))
    cy += line_h + 4

    # Mode
    mode_label = "Comparison" if mode == "comparison" else "Sandbox"
    surface.blit(font.render(f"Mode: {mode_label}", True, TEXT_COLOR), (cx, cy))
    cy += line_h

    # Stats
    surface.blit(font.render(f"Wave: {wave_count}", True, TEXT_COLOR), (cx, cy))
    cy += line_h
    surface.blit(font.render(f"Done: {complete_count}", True, TEXT_COLOR), (cx, cy))
    cy += line_h + 8

    # Duration
    surface.blit(font.render(f"Dur: {duration}t", True, TEXT_COLOR), (cx, cy))
    cy += line_h
    surface.blit(font.render(f"TPS: {tps}", True, TEXT_COLOR), (cx, cy))
    cy += line_h

    # Auto-wave
    auto_str = "ON" if auto_wave else "OFF"
    auto_color = (100, 255, 100) if auto_wave else TEXT_DIM
    surface.blit(font.render(f"Auto: {auto_str}", True, auto_color), (cx, cy))
    cy += line_h + 8

    # Selected easing (sandbox)
    if mode == "sandbox":
        surface.blit(font.render("Easing:", True, TEXT_DIM), (cx, cy))
        cy += line_h
        for i, name in enumerate(EASING_NAMES):
            color = EASING_COLORS[name] if name == selected_easing else TEXT_DIM
            prefix = "> " if name == selected_easing else "  "
            surface.blit(font.render(f"{prefix}{i + 1}:{name}", True, color), (cx, cy))
            cy += line_h - 2


def draw_status_bar(surface: pygame.Surface, font: pygame.font.Font, mode: str) -> None:
    """Draw bottom key-bindings bar."""
    y = LANE_H * LANE_COUNT
    pygame.draw.rect(surface, STATUS_BG, (0, y, SCREEN_W, STATUS_H))
    pygame.draw.line(surface, (50, 50, 70), (0, y), (SCREEN_W, y))

    if mode == "comparison":
        text = "[Space] Wave  [A] Auto  [+/-] Duration  [C] Clear  [Tab] Sandbox  [Esc] Quit"
    else:
        text = "[1-4] Easing  [Click] Spawn  [Space] Center  [A] Auto  [+/-] Dur  [C] Clear  [Tab] Compare  [Esc] Quit"

    label = font.render(text, True, TEXT_DIM)
    surface.blit(label, (8, y + STATUS_H // 2 - label.get_height() // 2))
