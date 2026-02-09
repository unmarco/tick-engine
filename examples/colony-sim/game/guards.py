"""FSM guards, event guards, and ability guards."""
from __future__ import annotations

from tick_colony import (
    FSMGuards, NeedHelper, NeedSet, EventGuards, AbilityGuards,
)
from tick_schedule import Timer


def make_fsm_guards(grid, stockpile_coord):
    """Create FSM guards for colonist AI."""
    fg = FSMGuards()
    fg.register("is_hungry", lambda w, e: NeedHelper.get_value(w.get(e, NeedSet), "hunger") < 40)
    fg.register("is_tired", lambda w, e: NeedHelper.get_value(w.get(e, NeedSet), "fatigue") < 40)
    fg.register("timer_done", lambda w, e: not w.has(e, Timer))
    fg.register("at_stockpile", lambda w, e: grid.position_of(e) == stockpile_coord)
    fg.register("always", lambda w, e: True)
    return fg


def make_event_guards():
    """Create event guards for seasonal conditions."""
    eg = EventGuards()
    eg.register("is_winter", lambda w, s: s.is_active("winter"))
    eg.register("is_summer", lambda w, s: s.is_active("summer"))
    eg.register("is_autumn", lambda w, s: s.is_active("autumn"))
    return eg


def make_ability_guards():
    """Create ability guards (none needed currently)."""
    return AbilityGuards()
