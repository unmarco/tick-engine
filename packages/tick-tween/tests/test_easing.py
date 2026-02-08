"""Tests for easing functions."""

from tick_tween import EASINGS


class TestLinearEasing:
    """Test linear easing function."""

    def test_linear_at_zero(self):
        """Linear easing should return 0 at t=0."""
        linear = EASINGS["linear"]
        assert linear(0.0) == 0.0

    def test_linear_at_half(self):
        """Linear easing should return 0.5 at t=0.5."""
        linear = EASINGS["linear"]
        assert linear(0.5) == 0.5

    def test_linear_at_one(self):
        """Linear easing should return 1 at t=1."""
        linear = EASINGS["linear"]
        assert linear(1.0) == 1.0


class TestEaseInEasing:
    """Test ease_in easing function."""

    def test_ease_in_at_zero(self):
        """Ease-in easing should return 0 at t=0."""
        ease_in = EASINGS["ease_in"]
        assert ease_in(0.0) == 0.0

    def test_ease_in_at_half(self):
        """Ease-in easing should return 0.25 at t=0.5 (t*t)."""
        ease_in = EASINGS["ease_in"]
        assert ease_in(0.5) == 0.25

    def test_ease_in_at_one(self):
        """Ease-in easing should return 1 at t=1."""
        ease_in = EASINGS["ease_in"]
        assert ease_in(1.0) == 1.0


class TestEaseOutEasing:
    """Test ease_out easing function."""

    def test_ease_out_at_zero(self):
        """Ease-out easing should return 0 at t=0."""
        ease_out = EASINGS["ease_out"]
        assert ease_out(0.0) == 0.0

    def test_ease_out_at_half(self):
        """Ease-out easing should return 0.75 at t=0.5 (t*(2-t))."""
        ease_out = EASINGS["ease_out"]
        assert ease_out(0.5) == 0.75

    def test_ease_out_at_one(self):
        """Ease-out easing should return 1 at t=1."""
        ease_out = EASINGS["ease_out"]
        assert ease_out(1.0) == 1.0


class TestEaseInOutEasing:
    """Test ease_in_out easing function."""

    def test_ease_in_out_at_zero(self):
        """Ease-in-out easing should return 0 at t=0."""
        ease_in_out = EASINGS["ease_in_out"]
        assert ease_in_out(0.0) == 0.0

    def test_ease_in_out_at_quarter(self):
        """Ease-in-out easing should return 0.125 at t=0.25 (2*t*t)."""
        ease_in_out = EASINGS["ease_in_out"]
        assert ease_in_out(0.25) == 0.125

    def test_ease_in_out_at_half(self):
        """Ease-in-out easing should return 0.5 at t=0.5."""
        ease_in_out = EASINGS["ease_in_out"]
        assert ease_in_out(0.5) == 0.5

    def test_ease_in_out_at_three_quarters(self):
        """Ease-in-out easing should return 0.875 at t=0.75."""
        ease_in_out = EASINGS["ease_in_out"]
        result = ease_in_out(0.75)
        assert abs(result - 0.875) < 1e-9

    def test_ease_in_out_at_one(self):
        """Ease-in-out easing should return 1 at t=1."""
        ease_in_out = EASINGS["ease_in_out"]
        assert ease_in_out(1.0) == 1.0


class TestEasingsDict:
    """Test EASINGS dictionary completeness."""

    def test_easings_contains_all_functions(self):
        """EASINGS dict should contain all four easing functions."""
        expected_keys = {"linear", "ease_in", "ease_out", "ease_in_out"}
        assert set(EASINGS.keys()) == expected_keys

    def test_easings_values_are_callable(self):
        """All EASINGS values should be callable functions."""
        for name, func in EASINGS.items():
            assert callable(func), f"{name} is not callable"

    def test_easings_map_zero_to_zero(self):
        """All easing functions should map 0 to 0."""
        for name, func in EASINGS.items():
            assert func(0.0) == 0.0, f"{name}(0) != 0"

    def test_easings_map_one_to_one(self):
        """All easing functions should map 1 to 1."""
        for name, func in EASINGS.items():
            result = func(1.0)
            assert abs(result - 1.0) < 1e-9, f"{name}(1) != 1"

    def test_easings_stay_in_unit_range(self):
        """All easing functions should map [0,1] to [0,1]."""
        test_values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for name, func in EASINGS.items():
            for t in test_values:
                result = func(t)
                assert 0.0 <= result <= 1.0, f"{name}({t}) = {result} is out of range [0,1]"
