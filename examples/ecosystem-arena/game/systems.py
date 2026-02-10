"""Custom system factories for the ecosystem arena.

All constants and spawn functions are passed as closure arguments to avoid
circular imports with setup.py.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

from tick_ai.components import Blackboard, UtilityAgent
from tick_physics import KinematicBody, vec

from game.components import Species, Visual

if TYPE_CHECKING:
    from tick import TickContext, World


def make_perception_system(
    perception_radius: float,
) -> Callable[["World", "TickContext"], None]:
    """Scan world and write nearest distances to each entity's blackboard."""
    pr_sq = perception_radius * perception_radius

    def perception_system(world: World, ctx: TickContext) -> None:
        # Collect all living entities with bodies + blackboards
        entities: list[tuple[int, str, tuple[float, ...]]] = []
        for eid, (body, sp) in world.query(KinematicBody, Species):
            entities.append((eid, sp.kind, body.position))

        for eid, (bb, sp, body) in world.query(Blackboard, Species, KinematicBody):
            my_pos = body.position
            my_kind = sp.kind

            if my_kind == "predator":
                nearest_prey_dist = float("inf")
                nearest_prey_eid = -1
                for oid, okind, opos in entities:
                    if oid == eid or okind != "prey":
                        continue
                    dsq = vec.distance_sq(my_pos, opos)
                    if dsq < nearest_prey_dist:
                        nearest_prey_dist = dsq
                        nearest_prey_eid = oid
                bb.data["nearest_prey_dist"] = math.sqrt(nearest_prey_dist) if nearest_prey_dist < float("inf") else float("inf")
                bb.data["nearest_prey_eid"] = nearest_prey_eid

            elif my_kind == "prey":
                nearest_pred_dist = float("inf")
                nearest_pred_eid = -1
                nearest_ally_dist = float("inf")
                for oid, okind, opos in entities:
                    if oid == eid:
                        continue
                    dsq = vec.distance_sq(my_pos, opos)
                    if okind == "predator" and dsq < nearest_pred_dist:
                        nearest_pred_dist = dsq
                        nearest_pred_eid = oid
                    elif okind == "prey" and dsq < nearest_ally_dist:
                        nearest_ally_dist = dsq
                bb.data["nearest_pred_dist"] = math.sqrt(nearest_pred_dist) if nearest_pred_dist < float("inf") else float("inf")
                bb.data["nearest_pred_eid"] = nearest_pred_eid
                bb.data["nearest_ally_dist"] = math.sqrt(nearest_ally_dist) if nearest_ally_dist < float("inf") else float("inf")

    return perception_system


def make_prey_action_system(
    flee_force: float,
    flock_force: float,
    graze_force: float,
) -> Callable[["World", "TickContext"], None]:
    """Read UtilityAgent.selected_action and apply the matching force."""

    def prey_action_system(world: World, ctx: TickContext) -> None:
        for eid, (agent, bb, body, sp) in world.query(
            UtilityAgent, Blackboard, KinematicBody, Species,
        ):
            if sp.kind != "prey":
                continue
            action = agent.selected_action
            if not action:
                continue

            if action == "flee":
                pred_eid = bb.data.get("nearest_pred_eid", -1)
                if pred_eid >= 0 and world.has(pred_eid, KinematicBody):
                    pred_body = world.get(pred_eid, KinematicBody)
                    away = vec.sub(body.position, pred_body.position)
                    mag = vec.magnitude(away)
                    if mag > 0.0:
                        direction = vec.normalize(away)
                        body.forces.append(vec.scale(direction, flee_force))

            elif action == "graze":
                # Slow down — apply gentle braking force
                speed = vec.magnitude(body.velocity)
                if speed > 5.0:
                    brake = vec.scale(vec.normalize(body.velocity), -graze_force)
                    body.forces.append(brake)

            elif action == "flock":
                # Move toward nearest ally
                ally_eid = _find_nearest_ally(world, eid, body.position)
                if ally_eid >= 0 and world.has(ally_eid, KinematicBody):
                    ally_body = world.get(ally_eid, KinematicBody)
                    toward = vec.sub(ally_body.position, body.position)
                    mag = vec.magnitude(toward)
                    if mag > 0.0:
                        direction = vec.normalize(toward)
                        body.forces.append(vec.scale(direction, flock_force))

    return prey_action_system


def _find_nearest_ally(world: "World", eid: int, pos: tuple[float, ...]) -> int:
    """Find nearest prey entity (excluding self)."""
    best_eid = -1
    best_dsq = float("inf")
    for oid, (body, sp) in world.query(KinematicBody, Species):
        if oid == eid or sp.kind != "prey":
            continue
        dsq = vec.distance_sq(pos, body.position)
        if dsq < best_dsq:
            best_dsq = dsq
            best_eid = oid
    return best_eid


def make_energy_system(
    drain_rate: float,
) -> Callable[["World", "TickContext"], None]:
    """Drain predator energy each tick and despawn starved predators."""

    def energy_system(world: World, ctx: TickContext) -> None:
        to_despawn: list[int] = []
        for eid, (bb, sp) in list(world.query(Blackboard, Species)):
            if sp.kind != "predator":
                continue
            energy = bb.data.get("energy", 0.0)
            energy -= drain_rate
            bb.data["energy"] = energy
            if energy <= 0.0:
                to_despawn.append(eid)
        for eid in to_despawn:
            world.despawn(eid)

    return energy_system


def make_reproduction_system(
    spawn_prey_fn: Callable[..., int],
    width: float,
    height: float,
    max_prey: int,
    graze_threshold: int,
) -> Callable[["World", "TickContext"], None]:
    """Increment graze timers for grazing prey, spawn offspring at threshold."""

    def reproduction_system(world: World, ctx: TickContext) -> None:
        prey_count = sum(1 for _, (sp,) in world.query(Species) if sp.kind == "prey")
        for eid, (agent, bb, body, sp) in list(
            world.query(UtilityAgent, Blackboard, KinematicBody, Species)
        ):
            if sp.kind != "prey":
                continue
            if agent.selected_action == "graze":
                timer = bb.data.get("graze_timer", 0)
                timer += 1
                bb.data["graze_timer"] = timer
                if timer >= graze_threshold and prey_count < max_prey:
                    bb.data["graze_timer"] = 0
                    # Spawn near parent
                    x, y = body.position
                    offset = 20.0
                    nx = min(max(x + ctx.random.uniform(-offset, offset), 30.0), width - 30.0)
                    ny = min(max(y + ctx.random.uniform(-offset, offset), 30.0), height - 30.0)
                    spawn_prey_fn(nx, ny)
                    prey_count += 1
            else:
                # Reset graze timer if not grazing
                bb.data["graze_timer"] = 0

    return reproduction_system


def make_boundary_system(
    width: float,
    height: float,
    restitution: float,
) -> Callable[["World", "TickContext"], None]:
    """Reflect velocity when entities hit screen edges."""

    def boundary_system(world: World, ctx: TickContext) -> None:
        for eid, (body, vis) in world.query(KinematicBody, Visual):
            x, y = body.position
            vx, vy = body.velocity
            margin = float(vis.radius)

            changed = False
            if x - margin < 0.0:
                x = margin
                vx = abs(vx) * restitution
                changed = True
            elif x + margin > width:
                x = width - margin
                vx = -abs(vx) * restitution
                changed = True

            if y - margin < 0.0:
                y = margin
                vy = abs(vy) * restitution
                changed = True
            elif y + margin > height:
                y = height - margin
                vy = -abs(vy) * restitution
                changed = True

            if changed:
                body.position = (x, y)
                body.velocity = (vx, vy)

    return boundary_system


def make_cleanup_system(
    pred_max_speed: float,
    prey_max_speed: float,
) -> Callable[["World", "TickContext"], None]:
    """Cap velocities (terminal velocity)."""

    def cleanup_system(world: World, ctx: TickContext) -> None:
        for eid, (body, sp) in world.query(KinematicBody, Species):
            max_spd = pred_max_speed if sp.kind == "predator" else prey_max_speed
            body.velocity = vec.clamp_magnitude(body.velocity, max_spd)

    return cleanup_system
