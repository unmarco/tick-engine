"""Tests for footprint utilities."""
from __future__ import annotations

import pytest
from tick_command.footprint import expand_footprint, resolve_footprint


class TestExpandFootprint:
    def test_1x1(self) -> None:
        assert expand_footprint((5, 3), (1, 1)) == [(5, 3)]

    def test_2x2(self) -> None:
        result = expand_footprint((5, 3), (2, 2))
        assert sorted(result) == sorted([(5, 3), (5, 4), (6, 3), (6, 4)])

    def test_3x1(self) -> None:
        result = expand_footprint((0, 0), (3, 1))
        assert sorted(result) == sorted([(0, 0), (1, 0), (2, 0)])

    def test_1x3(self) -> None:
        result = expand_footprint((0, 0), (1, 3))
        assert sorted(result) == sorted([(0, 0), (0, 1), (0, 2)])

    def test_negative_origin(self) -> None:
        result = expand_footprint((-1, -1), (2, 2))
        assert sorted(result) == sorted([(-1, -1), (-1, 0), (0, -1), (0, 0)])

    def test_3d(self) -> None:
        result = expand_footprint((0, 0, 0), (2, 1, 2))
        expected = [(0, 0, 0), (0, 0, 1), (1, 0, 0), (1, 0, 1)]
        assert sorted(result) == sorted(expected)

    def test_1d(self) -> None:
        result = expand_footprint((5,), (3,))
        assert result == [(5,), (6,), (7,)]

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensions"):
            expand_footprint((0, 0), (2, 2, 2))

    def test_zero_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 1"):
            expand_footprint((0, 0), (2, 0))

    def test_negative_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 1"):
            expand_footprint((0, 0), (-1, 2))


class TestResolveFootprint:
    def test_dimensions_tuple(self) -> None:
        result = resolve_footprint((5, 3), (2, 2))
        assert sorted(result) == sorted([(5, 3), (5, 4), (6, 3), (6, 4)])

    def test_offset_list(self) -> None:
        offsets = [(0, 0), (1, 0), (2, 0), (1, 1)]
        result = resolve_footprint((5, 3), offsets)
        assert sorted(result) == sorted([(5, 3), (6, 3), (7, 3), (6, 4)])

    def test_offset_list_empty(self) -> None:
        result = resolve_footprint((5, 3), [])
        assert result == []

    def test_offset_single(self) -> None:
        result = resolve_footprint((10, 20), [(0, 0)])
        assert result == [(10, 20)]

    def test_offset_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensions"):
            resolve_footprint((0, 0), [(0, 0, 0)])

    def test_3d_offsets(self) -> None:
        offsets = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        result = resolve_footprint((5, 3, 1), offsets)
        assert sorted(result) == sorted([(5, 3, 1), (6, 3, 1), (5, 4, 1)])

    def test_negative_offsets(self) -> None:
        offsets = [(0, 0), (-1, 0), (0, -1)]
        result = resolve_footprint((5, 5), offsets)
        assert sorted(result) == sorted([(5, 5), (4, 5), (5, 4)])
