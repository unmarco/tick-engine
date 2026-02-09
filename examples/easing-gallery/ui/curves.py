"""Easing curve plot renderer."""
from __future__ import annotations

import pygame

from tick_tween.easing import EASINGS

from ui.constants import CURVE_BG, EASING_COLORS, TEXT_DIM


def draw_curve_plot(
    surface: pygame.Surface,
    easing_name: str,
    x: int,
    y: int,
    w: int,
    h: int,
    current_t: float,
) -> None:
    """Draw an easing curve with a tracking dot."""
    pad = 10
    plot_x = x + pad
    plot_y = y + pad
    plot_w = w - 2 * pad
    plot_h = h - 2 * pad

    # Background
    pygame.draw.rect(surface, CURVE_BG, (x, y, w, h))

    # Axes
    pygame.draw.line(
        surface, TEXT_DIM, (plot_x, plot_y + plot_h), (plot_x + plot_w, plot_y + plot_h)
    )
    pygame.draw.line(surface, TEXT_DIM, (plot_x, plot_y + plot_h), (plot_x, plot_y))

    # Curve polyline
    easing_fn = EASINGS.get(easing_name)
    if easing_fn is None:
        return

    color = EASING_COLORS.get(easing_name, (200, 200, 200))
    samples = 80
    points = []
    for i in range(samples + 1):
        t = i / samples
        v = easing_fn(t)
        px = plot_x + t * plot_w
        py = plot_y + plot_h - v * plot_h
        points.append((px, py))

    if len(points) > 1:
        pygame.draw.lines(surface, color, False, points, 2)

    # Moving dot
    if 0.0 <= current_t <= 1.0:
        v = easing_fn(current_t)
        dot_x = int(plot_x + current_t * plot_w)
        dot_y = int(plot_y + plot_h - v * plot_h)
        pygame.draw.circle(surface, (255, 255, 255), (dot_x, dot_y), 4)
        pygame.draw.circle(surface, color, (dot_x, dot_y), 3)
