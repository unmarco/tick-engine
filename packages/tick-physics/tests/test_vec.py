"""Tests for N-dimensional vector math helpers."""
from __future__ import annotations

import math

import pytest

from tick_physics import vec


class TestAdd:
    def test_2d(self) -> None:
        assert vec.add((1.0, 2.0), (3.0, 4.0)) == (4.0, 6.0)

    def test_3d(self) -> None:
        assert vec.add((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)) == (5.0, 7.0, 9.0)

    def test_mismatched_dimensions_raises(self) -> None:
        with pytest.raises(ValueError):
            vec.add((1.0, 2.0), (3.0, 4.0, 5.0))


class TestSub:
    def test_2d(self) -> None:
        assert vec.sub((5.0, 3.0), (1.0, 2.0)) == (4.0, 1.0)

    def test_3d(self) -> None:
        assert vec.sub((5.0, 3.0, 1.0), (1.0, 2.0, 1.0)) == (4.0, 1.0, 0.0)


class TestScale:
    def test_scale_up(self) -> None:
        assert vec.scale((1.0, 2.0), 3.0) == (3.0, 6.0)

    def test_scale_zero(self) -> None:
        assert vec.scale((5.0, 10.0), 0.0) == (0.0, 0.0)

    def test_scale_negative(self) -> None:
        assert vec.scale((1.0, -2.0), -1.0) == (-1.0, 2.0)


class TestDot:
    def test_perpendicular(self) -> None:
        assert vec.dot((1.0, 0.0), (0.0, 1.0)) == 0.0

    def test_parallel(self) -> None:
        assert vec.dot((3.0, 0.0), (2.0, 0.0)) == 6.0

    def test_3d(self) -> None:
        assert vec.dot((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)) == 32.0


class TestMagnitude:
    def test_unit_x(self) -> None:
        assert vec.magnitude((1.0, 0.0)) == 1.0

    def test_3_4_5(self) -> None:
        assert vec.magnitude((3.0, 4.0)) == 5.0

    def test_zero(self) -> None:
        assert vec.magnitude((0.0, 0.0)) == 0.0

    def test_3d(self) -> None:
        assert vec.magnitude((1.0, 2.0, 2.0)) == 3.0


class TestMagnitudeSq:
    def test_basic(self) -> None:
        assert vec.magnitude_sq((3.0, 4.0)) == 25.0

    def test_avoids_sqrt(self) -> None:
        # magnitude_sq of (1,1,1) = 3, magnitude = sqrt(3)
        assert vec.magnitude_sq((1.0, 1.0, 1.0)) == 3.0


class TestNormalize:
    def test_unit_vector_unchanged(self) -> None:
        result = vec.normalize((1.0, 0.0))
        assert result == (1.0, 0.0)

    def test_scales_to_unit(self) -> None:
        result = vec.normalize((3.0, 4.0))
        assert math.isclose(result[0], 0.6)
        assert math.isclose(result[1], 0.8)
        assert math.isclose(vec.magnitude(result), 1.0)

    def test_zero_vector_returns_zero(self) -> None:
        assert vec.normalize((0.0, 0.0)) == (0.0, 0.0)

    def test_3d(self) -> None:
        result = vec.normalize((1.0, 2.0, 2.0))
        assert math.isclose(vec.magnitude(result), 1.0)


class TestDistance:
    def test_same_point(self) -> None:
        assert vec.distance((1.0, 2.0), (1.0, 2.0)) == 0.0

    def test_basic(self) -> None:
        assert vec.distance((0.0, 0.0), (3.0, 4.0)) == 5.0


class TestDistanceSq:
    def test_basic(self) -> None:
        assert vec.distance_sq((0.0, 0.0), (3.0, 4.0)) == 25.0


class TestZero:
    def test_2d(self) -> None:
        assert vec.zero(2) == (0.0, 0.0)

    def test_3d(self) -> None:
        assert vec.zero(3) == (0.0, 0.0, 0.0)

    def test_1d(self) -> None:
        assert vec.zero(1) == (0.0,)


class TestClampMagnitude:
    def test_under_limit_unchanged(self) -> None:
        v = (1.0, 0.0)
        assert vec.clamp_magnitude(v, 5.0) == v

    def test_at_limit_unchanged(self) -> None:
        v = (3.0, 4.0)
        assert vec.clamp_magnitude(v, 5.0) == v

    def test_over_limit_clamped(self) -> None:
        result = vec.clamp_magnitude((6.0, 8.0), 5.0)
        assert math.isclose(vec.magnitude(result), 5.0)
        assert math.isclose(result[0], 3.0)
        assert math.isclose(result[1], 4.0)

    def test_3d_clamped(self) -> None:
        result = vec.clamp_magnitude((2.0, 4.0, 4.0), 3.0)
        assert math.isclose(vec.magnitude(result), 3.0)
