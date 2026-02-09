"""Orb spawning utilities."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from tick_fsm import FSM
from tick_tween import Tween

from game.components import OrbState
from game.guards import TRANSITIONS
from ui.constants import (
    EASING_NAMES,
    LABEL_W,
    LANE_H,
    ORB_RADIUS,
    SCREEN_H,
    SCREEN_W,
    SIDEBAR_W,
    STATUS_H,
    TRACK_PAD,
    TRACK_W,
    CURVE_W,
)

if TYPE_CHECKING:
    from tick import World

# Target key for the tween system's registry lookup
_ORB_TARGET = f"{OrbState.__module__}.{OrbState.__qualname__}"


def spawn_orb(
    world: World,
    easing: str,
    lane: int,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    duration: int,
) -> int:
    """Spawn an orb entity with OrbState, Tween, and FSM components."""
    eid = world.spawn()
    world.attach(
        eid,
        OrbState(
            easing=easing,
            lane=lane,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
        ),
    )
    world.attach(
        eid,
        Tween(
            target=_ORB_TARGET,
            field="progress",
            start_val=0.0,
            end_val=1.0,
            duration=duration,
            easing=easing,
        ),
    )
    world.attach(eid, FSM(state="waiting", transitions=TRANSITIONS))
    return eid


def launch_wave(world: World, duration: int) -> list[int]:
    """Launch one orb per easing in comparison lanes 0-3."""
    eids = []
    track_left = LABEL_W + CURVE_W + TRACK_PAD
    track_right = LABEL_W + CURVE_W + TRACK_W - TRACK_PAD
    for i, easing in enumerate(EASING_NAMES):
        lane_y = i * LANE_H + LANE_H // 2
        eid = spawn_orb(
            world,
            easing=easing,
            lane=i,
            start_x=track_left,
            start_y=lane_y,
            end_x=track_right,
            end_y=lane_y,
            duration=duration,
        )
        eids.append(eid)
    return eids


def spawn_sandbox_orb(
    world: World, easing: str, mx: float, my: float, duration: int
) -> int:
    """Spawn a sandbox orb at cursor that tweens to a random target."""
    rng = random
    pad = ORB_RADIUS + 10
    playable_h = SCREEN_H - STATUS_H
    tx = rng.uniform(pad, SCREEN_W - SIDEBAR_W - pad)
    ty = rng.uniform(pad, playable_h - pad)
    return spawn_orb(
        world,
        easing=easing,
        lane=-1,
        start_x=mx,
        start_y=my,
        end_x=tx,
        end_y=ty,
        duration=duration,
    )
