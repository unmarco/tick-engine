"""Physics components and collision info."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KinematicBody:
    """Physics-enabled entity with position, velocity, mass, and force accumulator."""

    position: tuple[float, ...]
    velocity: tuple[float, ...]
    mass: float = 1.0
    forces: list[tuple[float, ...]] = field(default_factory=list)


@dataclass
class CircleCollider:
    """Sphere/circle collision shape. Center derived from KinematicBody.position."""

    radius: float


@dataclass
class AABBCollider:
    """Axis-aligned bounding box. Half-extents from center (KinematicBody.position)."""

    half_extents: tuple[float, ...]


@dataclass(frozen=True)
class Collision:
    """Collision info passed to callbacks. Not a component."""

    entity_a: int
    entity_b: int
    normal: tuple[float, ...]
    depth: float
