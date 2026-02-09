"""Sidebar panel — season, stats, abilities, selected colonist detail."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from game.abilities import ABILITY_KEYS, ABILITY_LABELS
from game.components import Colonist, SelectedTag
from tick_colony import NeedHelper, NeedSet, InventoryHelper, Inventory
from tick_fsm import FSM
from ui.constants import (
    COLOR_FATIGUE,
    COLOR_HUNGER,
    COLOR_NEED_BG,
    COLOR_SIDEBAR_BG,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    SEASON_TINTS,
)

if TYPE_CHECKING:
    from game.setup import GameState


def draw_sidebar(
    surface: pygame.Surface,
    font: pygame.font.Font,
    state: GameState,
    grid_px: int,
    sidebar_w: int,
) -> None:
    """Draw the right sidebar."""
    x0 = grid_px
    w = sidebar_w
    h = surface.get_height()

    # Background
    pygame.draw.rect(surface, COLOR_SIDEBAR_BG, (x0, 0, w, h))
    pygame.draw.line(surface, (50, 50, 60), (x0, 0), (x0, h))

    y = 8
    pad = x0 + 8

    # Season + year
    season = _current_season(state)
    tick = state.engine.clock.tick_number
    year = tick // 2000 + 1
    season_label = season.capitalize() if season else "---"
    _draw_text(surface, font, f"{season_label} - Year {year}", pad, y, COLOR_TEXT)
    y += 18

    # Tick count
    _draw_text(surface, font, f"Tick: {tick}", pad, y, COLOR_TEXT_DIM)
    y += 22

    # Population
    pop = len(list(state.engine.world.query(Colonist)))
    _draw_text(surface, font, f"Pop: {pop}/20", pad, y, COLOR_TEXT)
    y += 18

    # Food
    food = 0
    if state.engine.world.alive(state.stockpile_eid) and state.engine.world.has(state.stockpile_eid, Inventory):
        food = InventoryHelper.count(state.engine.world.get(state.stockpile_eid, Inventory), "food")
    cap = 60
    _draw_text(surface, font, f"Food: {food}/{cap}", pad, y, COLOR_TEXT)
    y += 26

    # Divider
    pygame.draw.line(surface, (50, 50, 60), (pad, y), (x0 + w - 8, y))
    y += 8

    # Abilities
    for aname in ("food_drop", "rally", "shelter"):
        label = ABILITY_LABELS[aname]
        key = ABILITY_KEYS[aname]
        defn = state.ability_mgr.definition(aname)
        st = state.ability_mgr.state(aname)
        if defn is None or st is None:
            continue

        # Status text
        if state.ability_mgr.is_active(aname):
            status = f"ACTIVE {st.active_remaining}t"
            color = (180, 120, 255)
        elif st.cooldown_remaining > 0:
            status = f"CD {st.cooldown_remaining}t"
            color = COLOR_TEXT_DIM
        else:
            status = "READY"
            color = (100, 220, 100)

        # Charges
        charge_str = ""
        if defn.max_charges != -1:
            charge_str = f" [{st.charges}]"

        _draw_text(surface, font, f"[{key}] {label}{charge_str}", pad, y, color)
        y += 14
        _draw_text(surface, font, f"     {status}", pad, y, color)
        y += 18

    y += 4
    # Divider
    pygame.draw.line(surface, (50, 50, 60), (pad, y), (x0 + w - 8, y))
    y += 8

    # Speed indicator
    speed_str = f"{state.speed:g}x"
    speed_label = "PAUSED" if state.paused else f"Speed: {speed_str}"
    speed_color = (255, 100, 100) if state.paused else COLOR_TEXT
    _draw_text(surface, font, speed_label, pad, y, speed_color)
    y += 22

    # Active events
    active_events = _active_world_events(state)
    if active_events:
        _draw_text(surface, font, "Events:", pad, y, (255, 160, 60))
        y += 16
        for ev_name in active_events:
            _draw_text(surface, font, f"  {ev_name.replace('_', ' ')}", pad, y, (255, 160, 60))
            y += 14
        y += 4

    # Divider
    pygame.draw.line(surface, (50, 50, 60), (pad, y), (x0 + w - 8, y))
    y += 8

    # Selected colonist detail
    _draw_text(surface, font, "-- Selected --", pad, y, COLOR_TEXT_DIM)
    y += 16

    if state.selected_eid is not None and state.engine.world.alive(state.selected_eid):
        eid = state.selected_eid
        w_obj = state.engine.world
        if w_obj.has(eid, Colonist):
            col = w_obj.get(eid, Colonist)
            fsm_state = w_obj.get(eid, FSM).state if w_obj.has(eid, FSM) else "?"
            _draw_text(surface, font, f"{col.name} ({fsm_state})", pad, y, COLOR_TEXT)
            y += 18

            if w_obj.has(eid, NeedSet):
                ns = w_obj.get(eid, NeedSet)
                hunger = NeedHelper.get_value(ns, "hunger")
                fatigue = NeedHelper.get_value(ns, "fatigue")

                # Hunger bar
                _draw_text(surface, font, "Hunger:", pad, y, COLOR_TEXT_DIM)
                y += 14
                bar_w = w - 24
                _draw_bar(surface, pad, y, bar_w, 8, hunger / 100.0, COLOR_HUNGER)
                y += 14

                # Fatigue bar
                _draw_text(surface, font, "Fatigue:", pad, y, COLOR_TEXT_DIM)
                y += 14
                _draw_bar(surface, pad, y, bar_w, 8, fatigue / 100.0, COLOR_FATIGUE)
                y += 14
    else:
        _draw_text(surface, font, "(none)", pad, y, COLOR_TEXT_DIM)


def _draw_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    rendered = font.render(text, True, color)
    surface.blit(rendered, (x, y))


def _draw_bar(
    surface: pygame.Surface,
    x: int, y: int, w: int, h: int,
    fraction: float,
    color: tuple[int, int, int],
) -> None:
    fraction = max(0.0, min(1.0, fraction))
    pygame.draw.rect(surface, COLOR_NEED_BG, (x, y, w, h))
    if fraction > 0:
        pygame.draw.rect(surface, color, (x, y, int(w * fraction), h))


def _current_season(state: GameState) -> str:
    """Get current season from the event scheduler."""
    for phase_name in ("spring", "summer", "autumn", "winter"):
        if state.sched.is_active(phase_name):
            return phase_name
    return "spring"


def _active_world_events(state: GameState) -> list[str]:
    """Get list of currently active world events."""
    events = []
    for name in ("cold_snap", "heat_wave", "bountiful_harvest", "raid", "plague"):
        if state.sched.is_active(name):
            events.append(name)
    return events
