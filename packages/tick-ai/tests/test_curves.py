"""Tests for response curves."""
import math

import pytest

from tick_ai.curves import inverse, linear, logistic, quadratic, step


class TestLinear:
    """Test linear response curve."""

    def test_linear_default(self):
        assert linear(0.0) == 0.0
        assert linear(0.5) == 0.5
        assert linear(1.0) == 1.0

    def test_linear_slope(self):
        assert linear(0.5, m=2.0) == 1.0
        assert linear(0.25, m=2.0) == 0.5
        assert linear(0.5, m=0.5) == 0.25

    def test_linear_offset(self):
        assert linear(0.0, b=0.5) == 0.5
        assert linear(0.5, b=0.2) == 0.7
        assert linear(0.0, b=1.0) == 1.0

    def test_linear_slope_and_offset(self):
        assert linear(0.5, m=2.0, b=0.1) == pytest.approx(1.0)  # clamped
        assert linear(0.2, m=2.0, b=0.1) == pytest.approx(0.5)

    def test_linear_clamping_above(self):
        assert linear(0.6, m=2.0) == 1.0
        assert linear(1.0, m=2.0) == 1.0
        assert linear(0.5, m=2.0, b=0.5) == 1.0

    def test_linear_clamping_below(self):
        assert linear(0.0, m=1.0, b=-0.5) == 0.0
        assert linear(0.5, m=-1.0) == 0.0

    def test_linear_input_clamping(self):
        assert linear(-0.5) == 0.0
        assert linear(1.5) == 1.0
        assert linear(-0.5, m=2.0, b=0.1) == pytest.approx(0.1)


class TestQuadratic:
    """Test quadratic (power) response curve."""

    def test_quadratic_default(self):
        assert quadratic(0.0) == 0.0
        assert quadratic(0.5) == pytest.approx(0.25)
        assert quadratic(1.0) == 1.0

    def test_quadratic_exponent_2(self):
        assert quadratic(0.5, exp=2.0) == pytest.approx(0.25)
        assert quadratic(0.25, exp=2.0) == pytest.approx(0.0625)

    def test_quadratic_exponent_3(self):
        assert quadratic(0.5, exp=3.0) == pytest.approx(0.125)
        assert quadratic(0.2, exp=3.0) == pytest.approx(0.008)

    def test_quadratic_exponent_half(self):
        assert quadratic(0.25, exp=0.5) == pytest.approx(0.5)
        assert quadratic(0.5, exp=0.5) == pytest.approx(math.sqrt(0.5))

    def test_quadratic_boundaries(self):
        assert quadratic(0.0, exp=5.0) == 0.0
        assert quadratic(1.0, exp=5.0) == 1.0

    def test_quadratic_input_clamping(self):
        assert quadratic(-0.5, exp=2.0) == 0.0
        assert quadratic(1.5, exp=2.0) == 1.0


class TestLogistic:
    """Test logistic (sigmoid) response curve."""

    def test_logistic_default(self):
        result = logistic(0.5)
        assert 0.4 < result < 0.6  # Should be near 0.5 at midpoint

    def test_logistic_boundaries(self):
        assert logistic(0.0) == pytest.approx(0.0, abs=0.01)
        assert logistic(1.0) == pytest.approx(1.0, abs=0.01)

    def test_logistic_midpoint(self):
        # At midpoint=0.5, value should be around 0.5
        assert logistic(0.5, k=10.0, midpoint=0.5) == pytest.approx(0.5, abs=0.05)
        # At midpoint=0.3, value should cross 0.5 at x=0.3
        assert logistic(0.3, k=10.0, midpoint=0.3) == pytest.approx(0.5, abs=0.05)

    def test_logistic_steepness(self):
        # Higher k means steeper transition
        steep = logistic(0.55, k=50.0, midpoint=0.5)
        gentle = logistic(0.55, k=5.0, midpoint=0.5)
        assert steep > gentle

    def test_logistic_input_clamping(self):
        # Negative inputs clamped to 0
        result = logistic(-0.5, k=10.0, midpoint=0.5)
        assert result == pytest.approx(0.0, abs=0.01)
        # Inputs > 1 clamped to 1
        result = logistic(1.5, k=10.0, midpoint=0.5)
        assert result == pytest.approx(1.0, abs=0.01)


class TestInverse:
    """Test inverse response curve."""

    def test_inverse_default(self):
        assert inverse(0.0) == 1.0
        assert inverse(0.5) == 0.5
        assert inverse(1.0) == 0.0

    def test_inverse_steepness_1(self):
        assert inverse(0.25, steepness=1.0) == 0.75
        assert inverse(0.75, steepness=1.0) == 0.25

    def test_inverse_steepness_2(self):
        assert inverse(0.5, steepness=2.0) == pytest.approx(0.75)
        assert inverse(0.25, steepness=2.0) == pytest.approx(0.9375)

    def test_inverse_boundaries(self):
        assert inverse(0.0, steepness=3.0) == 1.0
        assert inverse(1.0, steepness=3.0) == 0.0

    def test_inverse_input_clamping(self):
        assert inverse(-0.5) == 1.0
        assert inverse(1.5) == 0.0


class TestStep:
    """Test step response curve."""

    def test_step_default(self):
        assert step(0.0) == 0.0
        assert step(0.49) == 0.0
        assert step(0.5) == 1.0
        assert step(0.51) == 1.0
        assert step(1.0) == 1.0

    def test_step_threshold_low(self):
        assert step(0.0, threshold=0.2) == 0.0
        assert step(0.19, threshold=0.2) == 0.0
        assert step(0.2, threshold=0.2) == 1.0
        assert step(0.21, threshold=0.2) == 1.0

    def test_step_threshold_high(self):
        assert step(0.79, threshold=0.8) == 0.0
        assert step(0.8, threshold=0.8) == 1.0
        assert step(0.81, threshold=0.8) == 1.0

    def test_step_threshold_zero(self):
        assert step(0.0, threshold=0.0) == 1.0
        assert step(0.01, threshold=0.0) == 1.0

    def test_step_threshold_one(self):
        assert step(0.99, threshold=1.0) == 0.0
        assert step(1.0, threshold=1.0) == 1.0

    def test_step_input_clamping(self):
        assert step(-0.5, threshold=0.5) == 0.0
        assert step(1.5, threshold=0.5) == 1.0


class TestCurveClamping:
    """Test that all curves properly clamp inputs and outputs."""

    def test_all_curves_handle_negative_input(self):
        assert linear(-1.0) == 0.0
        assert quadratic(-1.0) == 0.0
        assert 0.0 <= logistic(-1.0) <= 0.1
        assert inverse(-1.0) == 1.0
        assert step(-1.0) == 0.0

    def test_all_curves_handle_large_input(self):
        assert linear(2.0) == 1.0
        assert quadratic(2.0) == 1.0
        assert 0.9 <= logistic(2.0) <= 1.0
        assert inverse(2.0) == 0.0
        assert step(2.0) == 1.0

    def test_all_curves_return_valid_range(self):
        for x in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert 0.0 <= linear(x) <= 1.0
            assert 0.0 <= quadratic(x) <= 1.0
            assert 0.0 <= logistic(x) <= 1.0
            assert 0.0 <= inverse(x) <= 1.0
            assert step(x) in (0.0, 1.0)
