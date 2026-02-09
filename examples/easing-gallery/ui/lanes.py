"""Comparison mode: lane-based rendering."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from tick_fsm import FSM

from game.components import OrbState
from ui.constants import (
    CURVE_W,
    EASING_COLORS,
    EASING_NAMES,
    LABEL_COLOR,
    LABEL_W,
    LANE_BG,
    LANE_BORDER,
    LANE_H,
    ORB_RADIUS,
    TRACK_BG,
    TRACK_PAD,
    TRACK_RAIL,
    TRACK_W,
)
from ui.curves import draw_curve_plot
from ui.orbs import draw_orb

if TYPE_CHECKING:
    from tick import World


def draw_lanes(surface: pygame.Surface, world: World, font: pygame.font.Font) -> None:
    """Draw comparison mode: 4 lanes with labels, curves, and orb tracks."""
    # Collect orbs by lane
    lane_orbs: dict[int, list[tuple[OrbState, str]]] = {i: [] for i in range(4)}
    for _eid, (orb, fsm) in world.query(OrbState, FSM):
        if 0 <= orb.lane < 4:
            lane_orbs[orb.lane].append((orb, fsm.state))

    # Find the "best" t for the curve dot per lane (latest active orb)
    lane_t: dict[int, float] = {}
    for lane_idx in range(4):
        best_t = -1.0
        for orb, state in lane_orbs[lane_idx]:
            if state == "animating":
                best_t = max(best_t, orb.t)
            elif state == "completed" and best_t < 0:
                best_t = orb.t
        lane_t[lane_idx] = best_t

    track_x = LABEL_W + CURVE_W

    for i, easing in enumerate(EASING_NAMES):
        lane_y = i * LANE_H

        # Lane background
        pygame.draw.rect(surface, LANE_BG, (0, lane_y, LABEL_W + CURVE_W + TRACK_W, LANE_H))
        pygame.draw.line(
            surface, LANE_BORDER, (0, lane_y + LANE_H - 1), (LABEL_W + CURVE_W + TRACK_W, lane_y + LANE_H - 1)
        )

        # Label
        label = font.render(easing, True, LABEL_COLOR)
        label_y = lane_y + LANE_H // 2 - label.get_height() // 2
        surface.blit(label, (10, label_y))

        # Curve plot
        curve_x = LABEL_W
        curve_y = lane_y + 10
        curve_h = LANE_H - 20
        draw_curve_plot(surface, easing, curve_x, curve_y, CURVE_W, curve_h, lane_t[i])

        # Track background
        pygame.draw.rect(surface, TRACK_BG, (track_x, lane_y, TRACK_W, LANE_H))

        # Track rail line
        rail_y = lane_y + LANE_H // 2
        rail_left = track_x + TRACK_PAD
        rail_right = track_x + TRACK_W - TRACK_PAD
        pygame.draw.line(surface, TRACK_RAIL, (rail_left, rail_y), (rail_right, rail_y), 2)

        # Start/end markers
        color = EASING_COLORS.get(easing, (200, 200, 200))
        dim_color = tuple(c // 3 for c in color)
        pygame.draw.circle(surface, dim_color, (rail_left, rail_y), 4)
        pygame.draw.circle(surface, dim_color, (rail_right, rail_y), 4)

        # Draw orbs in this lane
        for orb, state in lane_orbs[i]:
            ox = int(orb.start_x + (orb.end_x - orb.start_x) * orb.progress)
            oy = int(orb.start_y)
            draw_orb(surface, ox, oy, ORB_RADIUS, state, orb.easing)
