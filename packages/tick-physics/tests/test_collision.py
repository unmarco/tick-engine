"""Tests for pure collision detection functions (2D + 3D)."""
from __future__ import annotations

import math

from tick_physics.collision import aabb_vs_aabb, circle_vs_aabb, circle_vs_circle
from tick_physics.vec import Vec


# ── circle_vs_circle ──────────────────────────────────────────────


class TestCircleVsCircle:
    def test_no_overlap(self) -> None:
        result = circle_vs_circle((0.0, 0.0), 1.0, (3.0, 0.0), 1.0)
        assert result is None

    def test_touching_is_no_collision(self) -> None:
        result = circle_vs_circle((0.0, 0.0), 1.0, (2.0, 0.0), 1.0)
        assert result is None

    def test_overlapping(self) -> None:
        result = circle_vs_circle((0.0, 0.0), 1.0, (1.5, 0.0), 1.0)
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 0.5)
        assert math.isclose(normal[0], 1.0)
        assert math.isclose(normal[1], 0.0)

    def test_coincident_centers(self) -> None:
        result = circle_vs_circle((5.0, 5.0), 1.0, (5.0, 5.0), 1.0)
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 2.0)
        assert math.isclose(normal[0], 1.0)
        assert math.isclose(normal[1], 0.0)

    def test_3d_overlap(self) -> None:
        result = circle_vs_circle(
            (0.0, 0.0, 0.0), 2.0, (1.0, 0.0, 0.0), 2.0
        )
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 3.0)
        assert math.isclose(normal[0], 1.0)

    def test_3d_no_overlap(self) -> None:
        result = circle_vs_circle(
            (0.0, 0.0, 0.0), 1.0, (5.0, 5.0, 5.0), 1.0
        )
        assert result is None

    def test_normal_direction(self) -> None:
        """Normal points from A to B."""
        result = circle_vs_circle((0.0, 0.0), 1.0, (0.0, 1.5), 1.0)
        assert result is not None
        normal, _ = result
        assert math.isclose(normal[0], 0.0)
        assert math.isclose(normal[1], 1.0)

    def test_negative_positions(self) -> None:
        result = circle_vs_circle((-1.0, 0.0), 1.0, (0.0, 0.0), 1.0)
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 1.0)
        assert math.isclose(normal[0], 1.0)


# ── aabb_vs_aabb ─────────────────────────────────────────────────


class TestAABBVsAABB:
    def test_no_overlap(self) -> None:
        result = aabb_vs_aabb((0.0, 0.0), (1.0, 1.0), (5.0, 0.0), (1.0, 1.0))
        assert result is None

    def test_touching_is_no_collision(self) -> None:
        result = aabb_vs_aabb((0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (1.0, 1.0))
        assert result is None

    def test_overlapping_x(self) -> None:
        result = aabb_vs_aabb((0.0, 0.0), (1.0, 1.0), (1.5, 0.0), (1.0, 1.0))
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 0.5)
        assert math.isclose(normal[0], 1.0)
        assert math.isclose(normal[1], 0.0)

    def test_overlapping_y(self) -> None:
        result = aabb_vs_aabb((0.0, 0.0), (1.0, 1.0), (0.0, 1.5), (1.0, 1.0))
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 0.5)
        assert math.isclose(normal[0], 0.0)
        assert math.isclose(normal[1], 1.0)

    def test_fully_contained(self) -> None:
        result = aabb_vs_aabb((0.0, 0.0), (5.0, 5.0), (0.0, 0.0), (1.0, 1.0))
        assert result is not None
        _, depth = result
        assert depth > 0.0

    def test_3d_overlap(self) -> None:
        result = aabb_vs_aabb(
            (0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
            (1.5, 0.0, 0.0), (1.0, 1.0, 1.0),
        )
        assert result is not None
        normal, depth = result
        assert math.isclose(depth, 0.5)
        assert math.isclose(normal[0], 1.0)

    def test_3d_no_overlap(self) -> None:
        result = aabb_vs_aabb(
            (0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
            (5.0, 5.0, 5.0), (1.0, 1.0, 1.0),
        )
        assert result is None

    def test_minimum_penetration_axis(self) -> None:
        """Normal should be along the axis with minimum overlap."""
        result = aabb_vs_aabb(
            (0.0, 0.0), (1.0, 1.0), (1.5, 0.5), (1.0, 1.0)
        )
        assert result is not None
        normal, depth = result
        # x overlap = (1+1) - 1.5 = 0.5, y overlap = (1+1) - 0.5 = 1.5
        assert math.isclose(depth, 0.5)
        assert math.isclose(normal[0], 1.0)
        assert math.isclose(normal[1], 0.0)


# ── circle_vs_aabb ───────────────────────────────────────────────


class TestCircleVsAABB:
    def test_no_overlap(self) -> None:
        result = circle_vs_aabb(
            (5.0, 0.0), 1.0, (0.0, 0.0), (1.0, 1.0)
        )
        assert result is None

    def test_overlapping_from_side(self) -> None:
        # Circle at x=1.4, radius 0.6. AABB edge at x=1.0. Overlap = 0.6 - 0.4 = 0.2.
        result = circle_vs_aabb(
            (1.4, 0.0), 0.6, (0.0, 0.0), (1.0, 1.0)
        )
        assert result is not None
        normal, depth = result
        assert depth > 0.0
        # Circle is to the right of AABB, normal from circle toward AABB.
        assert normal[0] < 0.0

    def test_circle_center_inside_aabb(self) -> None:
        result = circle_vs_aabb(
            (0.0, 0.0), 0.5, (0.0, 0.0), (2.0, 2.0)
        )
        assert result is not None
        _, depth = result
        assert depth > 0.0

    def test_circle_touching_corner(self) -> None:
        # Circle at (2, 2), radius 1.5 vs AABB centered at (0,0) with half (1,1).
        # Corner at (1,1), distance = sqrt(2) ≈ 1.414, radius 1.5 > 1.414.
        result = circle_vs_aabb(
            (2.0, 2.0), 1.5, (0.0, 0.0), (1.0, 1.0)
        )
        assert result is not None
        normal, depth = result
        assert depth > 0.0

    def test_3d_overlap(self) -> None:
        result = circle_vs_aabb(
            (2.5, 0.0, 0.0), 1.0,
            (0.0, 0.0, 0.0), (2.0, 2.0, 2.0),
        )
        assert result is not None
        normal, depth = result
        assert depth > 0.0

    def test_3d_no_overlap(self) -> None:
        result = circle_vs_aabb(
            (10.0, 10.0, 10.0), 1.0,
            (0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
        )
        assert result is None
