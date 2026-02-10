"""tick-physics - N-dimensional kinematics and collision detection for the tick engine."""
from __future__ import annotations

from tick_physics import vec
from tick_physics.components import AABBCollider, CircleCollider, Collision, KinematicBody
from tick_physics.systems import make_collision_system, make_physics_system

__all__ = [
    "AABBCollider",
    "CircleCollider",
    "Collision",
    "KinematicBody",
    "make_collision_system",
    "make_physics_system",
    "vec",
]
