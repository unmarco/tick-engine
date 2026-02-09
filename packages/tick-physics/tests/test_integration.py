"""Integration tests: full physics pipeline, snapshot/restore, edge cases."""
from __future__ import annotations

import math

from tick import Engine
from tick_physics import vec
from tick_physics.components import (
    AABBCollider,
    CircleCollider,
    Collision,
    KinematicBody,
)
from tick_physics.systems import make_collision_system, make_physics_system


class TestFullPipeline:
    """Forces + movement + collision detection in a single simulation."""

    def test_gravity_causes_falling(self) -> None:
        engine = Engine(tps=60, seed=42)
        world = engine.world
        world.register_component(KinematicBody)

        ball = world.spawn()
        world.attach(
            ball,
            KinematicBody(position=(0.0, 100.0), velocity=(0.0, 0.0)),
        )

        def gravity(world, ctx):  # type: ignore[no-untyped-def]
            for eid, (body,) in world.query(KinematicBody):
                body.forces.append((0.0, -9.8 * body.mass))

        engine.add_system(gravity)
        engine.add_system(make_physics_system())
        engine.run(60)  # 1 second at 60 TPS

        body = world.get(ball, KinematicBody)
        # After 1 second of gravity: y ≈ 100 - 0.5*9.8*1² ≈ 95.1
        assert body.position[1] < 100.0
        assert body.velocity[1] < 0.0

    def test_projectile_motion(self) -> None:
        engine = Engine(tps=100, seed=42)
        world = engine.world
        world.register_component(KinematicBody)

        proj = world.spawn()
        world.attach(
            proj,
            KinematicBody(
                position=(0.0, 0.0), velocity=(10.0, 20.0)
            ),
        )

        def gravity(world, ctx):  # type: ignore[no-untyped-def]
            for eid, (body,) in world.query(KinematicBody):
                body.forces.append((0.0, -10.0 * body.mass))

        engine.add_system(gravity)
        engine.add_system(make_physics_system())
        engine.run(100)  # 1 second

        body = world.get(proj, KinematicBody)
        # x ≈ 10*1 = 10, y ≈ 20*1 - 0.5*10*1 ≈ 15
        assert math.isclose(body.position[0], 10.0, abs_tol=0.2)
        assert body.position[1] > 0.0  # Still above ground

    def test_collision_callback_can_modify_world(self) -> None:
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)
        world.register_component(CircleCollider)

        a = world.spawn()
        world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(5.0, 0.0))
        )
        world.attach(a, CircleCollider(radius=1.0))

        b = world.spawn()
        world.attach(
            b, KinematicBody(position=(1.5, 0.0), velocity=(-5.0, 0.0))
        )
        world.attach(b, CircleCollider(radius=1.0))

        def stop_on_collision(world, ctx, col):  # type: ignore[no-untyped-def]
            body_a = world.get(col.entity_a, KinematicBody)
            body_b = world.get(col.entity_b, KinematicBody)
            body_a.velocity = (0.0, 0.0)
            body_b.velocity = (0.0, 0.0)

        engine.add_system(make_physics_system())
        engine.add_system(make_collision_system(stop_on_collision))
        engine.step()

        body_a = world.get(a, KinematicBody)
        body_b = world.get(b, KinematicBody)
        assert body_a.velocity == (0.0, 0.0)
        assert body_b.velocity == (0.0, 0.0)

    def test_forces_from_multiple_systems(self) -> None:
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)

        eid = world.spawn()
        world.attach(
            eid, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )

        def gravity(world, ctx):  # type: ignore[no-untyped-def]
            for eid, (body,) in world.query(KinematicBody):
                body.forces.append((0.0, -10.0))

        def wind(world, ctx):  # type: ignore[no-untyped-def]
            for eid, (body,) in world.query(KinematicBody):
                body.forces.append((5.0, 0.0))

        engine.add_system(gravity)
        engine.add_system(wind)
        engine.add_system(make_physics_system())
        engine.step()

        body = world.get(eid, KinematicBody)
        # net force = (5, -10), a = (5, -10), v = (0.5, -1.0), pos = (0.05, -0.1)
        assert math.isclose(body.velocity[0], 0.5)
        assert math.isclose(body.velocity[1], -1.0)


class TestSnapshotRestore:
    def test_kinematic_body_survives_snapshot(self) -> None:
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)
        world.register_component(CircleCollider)

        eid = world.spawn()
        world.attach(
            eid,
            KinematicBody(
                position=(1.0, 2.0), velocity=(3.0, 4.0), mass=5.0
            ),
        )
        world.attach(eid, CircleCollider(radius=2.5))

        snap = engine.snapshot()

        engine2 = Engine(tps=10, seed=42)
        engine2.world.register_component(KinematicBody)
        engine2.world.register_component(CircleCollider)
        engine2.restore(snap)

        body = engine2.world.get(eid, KinematicBody)
        assert body.position == (1.0, 2.0)
        assert body.velocity == (3.0, 4.0)
        assert body.mass == 5.0
        assert body.forces == []

        collider = engine2.world.get(eid, CircleCollider)
        assert collider.radius == 2.5

    def test_aabb_collider_survives_snapshot(self) -> None:
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)
        world.register_component(AABBCollider)

        eid = world.spawn()
        world.attach(
            eid,
            KinematicBody(position=(0.0, 0.0, 0.0), velocity=(1.0, 2.0, 3.0)),
        )
        world.attach(eid, AABBCollider(half_extents=(1.0, 2.0, 3.0)))

        snap = engine.snapshot()

        engine2 = Engine(tps=10, seed=42)
        engine2.world.register_component(KinematicBody)
        engine2.world.register_component(AABBCollider)
        engine2.restore(snap)

        body = engine2.world.get(eid, KinematicBody)
        assert body.position == (0.0, 0.0, 0.0)
        assert body.velocity == (1.0, 2.0, 3.0)

        collider = engine2.world.get(eid, AABBCollider)
        assert collider.half_extents == (1.0, 2.0, 3.0)


class TestEdgeCases:
    def test_zero_mass_raises(self) -> None:
        """Division by zero if mass is 0 — user responsibility, but test behavior."""
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)

        eid = world.spawn()
        body = KinematicBody(
            position=(0.0, 0.0), velocity=(0.0, 0.0), mass=0.0
        )
        world.attach(eid, body)
        engine.add_system(make_physics_system())
        body.forces.append((1.0, 0.0))
        # Zero mass causes division by zero — raises ZeroDivisionError.
        try:
            engine.step()
            assert False, "Expected ZeroDivisionError"
        except ZeroDivisionError:
            pass

    def test_very_high_velocity(self) -> None:
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)

        eid = world.spawn()
        world.attach(
            eid,
            KinematicBody(
                position=(0.0, 0.0), velocity=(1e6, 0.0)
            ),
        )
        engine.add_system(make_physics_system())
        engine.step()
        body = world.get(eid, KinematicBody)
        assert math.isclose(body.position[0], 1e5)

    def test_many_entities(self) -> None:
        """Smoke test with many entities — verifies no errors with larger sets."""
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)
        world.register_component(CircleCollider)

        collisions: list[Collision] = []
        for i in range(50):
            e = world.spawn()
            world.attach(
                e,
                KinematicBody(
                    position=(float(i * 10), 0.0), velocity=(1.0, 0.0)
                ),
            )
            world.attach(e, CircleCollider(radius=0.5))

        engine.add_system(make_physics_system())
        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.run(5)
        # Entities are spaced 10 apart with radius 0.5 — no collisions.
        assert len(collisions) == 0

    def test_despawned_entity_not_in_query(self) -> None:
        engine = Engine(tps=10, seed=42)
        world = engine.world
        world.register_component(KinematicBody)
        world.register_component(CircleCollider)

        collisions: list[Collision] = []

        a = world.spawn()
        world.attach(
            a, KinematicBody(position=(0.0, 0.0), velocity=(0.0, 0.0))
        )
        world.attach(a, CircleCollider(radius=2.0))

        b = world.spawn()
        world.attach(
            b, KinematicBody(position=(1.0, 0.0), velocity=(0.0, 0.0))
        )
        world.attach(b, CircleCollider(radius=2.0))

        world.despawn(b)

        engine.add_system(
            make_collision_system(lambda w, c, col: collisions.append(col))
        )
        engine.step()
        assert len(collisions) == 0


class TestVecModule:
    """Test that vec is accessible from the package."""

    def test_vec_re_exported(self) -> None:
        from tick_physics import vec as v

        assert v.add((1.0, 2.0), (3.0, 4.0)) == (4.0, 6.0)
