"""System factories for physics simulation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick.filters import AnyOf

from tick_physics import vec
from tick_physics.collision import aabb_vs_aabb, circle_vs_aabb, circle_vs_circle
from tick_physics.components import AABBCollider, CircleCollider, Collision, KinematicBody

if TYPE_CHECKING:
    from tick import TickContext, World


def make_physics_system() -> Callable[["World", "TickContext"], None]:
    """Semi-implicit Euler integrator: forces → velocity → position.

    Forces are cleared after processing. Entities with no forces still
    move (velocity persists).
    """

    def physics_system(world: "World", ctx: "TickContext") -> None:
        for eid, (body,) in world.query(KinematicBody):
            if body.forces:
                net = body.forces[0]
                for f in body.forces[1:]:
                    net = vec.add(net, f)
                acceleration = vec.scale(net, 1.0 / body.mass)
                body.velocity = vec.add(
                    body.velocity, vec.scale(acceleration, ctx.dt)
                )
                body.forces.clear()
            body.position = vec.add(
                body.position, vec.scale(body.velocity, ctx.dt)
            )

    return physics_system


_CollisionPair = tuple[type, type]
_DetectFn = Callable[..., tuple[tuple[float, ...], float] | None]


def _dispatch(
    pos_a: tuple[float, ...],
    shape_a: CircleCollider | AABBCollider,
    pos_b: tuple[float, ...],
    shape_b: CircleCollider | AABBCollider,
) -> tuple[tuple[float, ...], float] | None:
    """Dispatch to the correct collision detection function."""
    if isinstance(shape_a, CircleCollider) and isinstance(shape_b, CircleCollider):
        return circle_vs_circle(pos_a, shape_a.radius, pos_b, shape_b.radius)
    if isinstance(shape_a, AABBCollider) and isinstance(shape_b, AABBCollider):
        return aabb_vs_aabb(pos_a, shape_a.half_extents, pos_b, shape_b.half_extents)
    if isinstance(shape_a, CircleCollider) and isinstance(shape_b, AABBCollider):
        result = circle_vs_aabb(pos_a, shape_a.radius, pos_b, shape_b.half_extents)
        return result
    if isinstance(shape_a, AABBCollider) and isinstance(shape_b, CircleCollider):
        result = circle_vs_aabb(pos_b, shape_b.radius, pos_a, shape_a.half_extents)
        if result is None:
            return None
        # Flip normal: the function returns normal from circle toward AABB,
        # but we need A→B direction.
        normal, depth = result
        normal = tuple(-n for n in normal)
        return normal, depth
    return None


def make_collision_system(
    on_collision: Callable[["World", "TickContext", Collision], None],
) -> Callable[["World", "TickContext"], None]:
    """Detect collisions between entities with colliders. O(n^2) broadphase.

    Fires on_collision for each detected overlap. The callback decides
    what to do (bounce, destroy, knockback, ignore).
    """

    def collision_system(world: "World", ctx: "TickContext") -> None:
        entities: list[
            tuple[int, KinematicBody, CircleCollider | AABBCollider]
        ] = []
        for eid, (body,) in world.query(
            KinematicBody, AnyOf(CircleCollider, AABBCollider)
        ):
            if world.has(eid, CircleCollider):
                entities.append((eid, body, world.get(eid, CircleCollider)))
            elif world.has(eid, AABBCollider):
                entities.append((eid, body, world.get(eid, AABBCollider)))

        for i in range(len(entities)):
            eid_a, body_a, shape_a = entities[i]
            for j in range(i + 1, len(entities)):
                eid_b, body_b, shape_b = entities[j]
                result = _dispatch(
                    body_a.position, shape_a, body_b.position, shape_b
                )
                if result is not None:
                    normal, depth = result
                    on_collision(
                        world,
                        ctx,
                        Collision(eid_a, eid_b, normal, depth),
                    )

    return collision_system
