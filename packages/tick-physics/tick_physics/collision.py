"""Pure collision detection functions. N-dimensional."""
from __future__ import annotations

import math

from tick_physics.vec import Vec


def circle_vs_circle(
    pos_a: Vec,
    radius_a: float,
    pos_b: Vec,
    radius_b: float,
) -> tuple[Vec, float] | None:
    """Detect circle/sphere overlap. Returns (normal A→B, depth) or None."""
    dist_sq = sum((a - b) ** 2 for a, b in zip(pos_a, pos_b, strict=True))
    r_sum = radius_a + radius_b
    if dist_sq >= r_sum * r_sum:
        return None
    dist = math.sqrt(dist_sq)
    if dist == 0.0:
        # Coincident centers — pick arbitrary normal along first axis.
        normal = tuple(1.0 if i == 0 else 0.0 for i in range(len(pos_a)))
        return normal, r_sum
    inv_dist = 1.0 / dist
    normal = tuple((b - a) * inv_dist for a, b in zip(pos_a, pos_b, strict=True))
    return normal, r_sum - dist


def aabb_vs_aabb(
    pos_a: Vec,
    half_a: Vec,
    pos_b: Vec,
    half_b: Vec,
) -> tuple[Vec, float] | None:
    """Detect AABB overlap. Returns (normal A→B, depth) on minimum-penetration axis or None."""
    min_overlap = float("inf")
    min_axis = -1
    min_sign = 1.0
    ndim = len(pos_a)

    for i in range(ndim):
        overlap = (half_a[i] + half_b[i]) - abs(pos_a[i] - pos_b[i])
        if overlap <= 0.0:
            return None
        if overlap < min_overlap:
            min_overlap = overlap
            min_axis = i
            min_sign = 1.0 if pos_b[i] >= pos_a[i] else -1.0

    normal = tuple(
        min_sign if i == min_axis else 0.0 for i in range(ndim)
    )
    return normal, min_overlap


def circle_vs_aabb(
    circle_pos: Vec,
    radius: float,
    aabb_pos: Vec,
    half_extents: Vec,
) -> tuple[Vec, float] | None:
    """Detect circle/sphere vs AABB overlap. Returns (normal A→B, depth) or None."""
    ndim = len(circle_pos)
    # Clamp circle center to AABB bounds to find closest point.
    closest = tuple(
        max(aabb_pos[i] - half_extents[i], min(circle_pos[i], aabb_pos[i] + half_extents[i]))
        for i in range(ndim)
    )
    dist_sq = sum((circle_pos[i] - closest[i]) ** 2 for i in range(ndim))

    if dist_sq >= radius * radius:
        return None

    if dist_sq == 0.0:
        # Circle center is inside the AABB — use minimum-penetration axis.
        min_pen = float("inf")
        min_axis = 0
        min_sign = 1.0
        for i in range(ndim):
            pen_pos = (aabb_pos[i] + half_extents[i]) - circle_pos[i]
            pen_neg = circle_pos[i] - (aabb_pos[i] - half_extents[i])
            if pen_pos < min_pen:
                min_pen = pen_pos
                min_axis = i
                min_sign = 1.0
            if pen_neg < min_pen:
                min_pen = pen_neg
                min_axis = i
                min_sign = -1.0
        normal = tuple(min_sign if i == min_axis else 0.0 for i in range(ndim))
        depth = radius + min_pen
        return normal, depth

    dist = math.sqrt(dist_sq)
    inv_dist = 1.0 / dist
    # Normal points from circle toward AABB (closest point).
    normal = tuple((closest[i] - circle_pos[i]) * inv_dist for i in range(ndim))
    depth = radius - dist
    return normal, depth
