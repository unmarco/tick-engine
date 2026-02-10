"""Tests for physics and collision system factories."""
from __future__ import annotations

import math
import random

from tick import Engine
from tick_physics import vec
from tick_physics.components import (
    AABBCollider,
    CircleCollider,
    Collision,
    KinematicBody,
)
from tick_physics.systems import make_collision_system, make_physics_system


# ── Physics System ─────────────────────────────────────────────


class TestPhysicsSystem:
    def _make_engine(self, tps: int = 10) -> Engine:
        engine = Engine(tps=tps, seed=42)
        engine.world.register_component(KinematicBody)
        return engine

    def test_velocity_moves_position(self) -> None:
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            KinematicBody(position=(0.0, 0.0), velocity=(10.0, 0.0)),
        )
        engine.add_system(make_physics_system())
        engine.step()
        body = engine.world.get(eid, KinematicBody)
        # dt = 1/10 = 0.1, position = 0 + 10*0.1 = 1.0
        assert math.isclose(body.position[0], 1.0)
        assert math.isclose(body.position[1], 0.0)

    def test_force_accelerates(self) -> None:
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        body = KinematicBody(
            position=(0.0, 0.0), velocity=(0.0, 0.0), mass=2.0
        )
        engine.world.attach(eid, body)
        engine.add_system(make_physics_system())
        body.forces.append((20.0, 0.0))
        engine.step()
        result = engine.world.get(eid, KinematicBody)
        # a = F/m = 20/2 = 10, v = 0 + 10*0.1 = 1.0, pos = 0 + 1.0*0.1 = 0.1
        assert math.isclose(result.velocity[0], 1.0)
        assert math.isclose(result.position[0], 0.1)

    def test_forces_cleared_after_step(self) -> None:
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        body = KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        engine.world.attach(eid, body)
        engine.add_system(make_physics_system())
        body.forces.append((10.0, 0.0))
        engine.step()
        result = engine.world.get(eid, KinematicBody)
        assert len(result.forces) == 0

    def test_multiple_forces_accumulated(self) -> None:
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        body = KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        engine.world.attach(eid, body)
        engine.add_system(make_physics_system())
        body.forces.append((5.0, 0.0))
        body.forces.append((5.0, 0.0))
        engine.step()
        result = engine.world.get(eid, KinematicBody)
        # net force = 10, a = 10/1 = 10, v = 1.0, pos = 0.1
        assert math.isclose(result.velocity[0], 1.0)

    def test_no_force_velocity_persists(self) -> None:
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            KinematicBody(position=(0.0, 0.0), velocity=(5.0, 0.0)),
        )
        engine.add_system(make_physics_system())
        engine.run(3)
        body = engine.world.get(eid, KinematicBody)
        # After 3 steps: pos = 5 * 0.1 * 3 = 1.5
        assert math.isclose(body.position[0], 1.5)
        assert math.isclose(body.velocity[0], 5.0)

    def test_3d_movement(self) -> None:
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        engine.world.attach(
            eid,
            KinematicBody(
                position=(0.0, 0.0, 0.0), velocity=(1.0, 2.0, 3.0)
            ),
        )
        engine.add_system(make_physics_system())
        engine.step()
        body = engine.world.get(eid, KinematicBody)
        assert math.isclose(body.position[0], 0.1)
        assert math.isclose(body.position[1], 0.2)
        assert math.isclose(body.position[2], 0.3)

    def test_semi_implicit_euler(self) -> None:
        """Velocity updates before position — tests semi-implicit Euler."""
        engine = self._make_engine(tps=10)
        eid = engine.world.spawn()
        body = KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        engine.world.attach(eid, body)
        engine.add_system(make_physics_system())
        body.forces.append((10.0, 0.0))
        engine.step()
        result = engine.world.get(eid, KinematicBody)
        # Semi-implicit: v = 0 + 10*0.1 = 1.0, then pos = 0 + 1.0*0.1 = 0.1
        # Explicit would be: pos = 0 + 0*0.1 = 0 (old velocity)
        assert math.isclose(result.position[0], 0.1)


# ── Collision System ───────────────────────────────────────────


class TestCollisionSystem:
    def _make_engine(self, tps: int = 10) -> Engine:
        engine = Engine(tps=tps, seed=42)
        engine.world.register_component(KinematicBody)
        engine.world.register_component(CircleCollider)
        engine.world.register_component(AABBCollider)
        return engine

    def test_circle_circle_collision_fires(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(a, CircleCollider(radius=1.0))

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(1.5, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, CircleCollider(radius=1.0))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 1
        assert collisions[0].entity_a == a
        assert collisions[0].entity_b == b
        assert collisions[0].depth > 0.0

    def test_no_collision_when_far_apart(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(a, CircleCollider(radius=1.0))

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(10.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, CircleCollider(radius=1.0))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 0

    def test_aabb_aabb_collision(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(a, AABBCollider(half_extents=(1.0, 1.0)))

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(1.5, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, AABBCollider(half_extents=(1.0, 1.0)))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 1

    def test_circle_aabb_collision(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(a, CircleCollider(radius=1.0))

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(1.5, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, AABBCollider(half_extents=(1.0, 1.0)))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 1

    def test_aabb_circle_collision(self) -> None:
        """Reversed order: AABB entity first, circle second."""
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(a, AABBCollider(half_extents=(1.0, 1.0)))

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(1.5, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, CircleCollider(radius=1.0))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 1

    def test_entity_without_collider_ignored(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        # No collider — should not participate in collision detection.

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(0.5, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, CircleCollider(radius=1.0))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 0

    def test_multiple_collisions_detected(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        # Three circles all overlapping.
        for x in (0.0, 1.0, 2.0):
            e = engine.world.spawn()
            engine.world.attach(
                e, KinematicBody(position=(x, 0.0), velocity=(0.0, 0.0))
            )
            engine.world.attach(e, CircleCollider(radius=1.0))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        # Pairs: (0,1), (0,2), (1,2). 0-1 overlap, 1-2 overlap, 0-2 touching (no collision).
        assert len(collisions) == 2

    def test_each_pair_checked_once(self) -> None:
        engine = self._make_engine()
        collisions: list[Collision] = []

        a = engine.world.spawn()
        engine.world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(a, CircleCollider(radius=2.0))

        b = engine.world.spawn()
        engine.world.attach(
            b, KinematicBody(position=(1.0, 0.0), velocity=(0.0, 0.0))
        )
        engine.world.attach(b, CircleCollider(radius=2.0))

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 1
