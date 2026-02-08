"""
Test suite for HexGrid spatial indexing.

Tests cover:
- Constructor and properties
- Entity placement and retrieval
- Bounds checking (axial coordinates)
- Hex neighbor topology (6-directional)
- Hex distance calculations
- Radius queries
- Heuristic calculations
- World rebuild functionality
"""

import pytest
from tick_spatial import Pos2D, HexGrid
from tick import Engine


class TestHexGridConstruction:
    """Test HexGrid initialization and properties."""

    def test_constructor_sets_dimensions(self):
        hex_grid = HexGrid(width=10, height=10)
        assert hex_grid.width == 10
        assert hex_grid.height == 10

    def test_constructor_different_dimensions(self):
        hex_grid = HexGrid(width=15, height=20)
        assert hex_grid.width == 15
        assert hex_grid.height == 20


class TestHexGridPlacement:
    """Test entity placement operations."""

    def test_place_and_retrieve_entity(self):
        hex_grid = HexGrid(width=10, height=10)
        eid = 1
        hex_grid.place(eid, 5, 5)

        entities = hex_grid.at(5, 5)
        assert eid in entities
        assert hex_grid.position_of(eid) == (5, 5)

    def test_place_at_zero_zero(self):
        hex_grid = HexGrid(width=10, height=10)
        eid = 1
        hex_grid.place(eid, 0, 0)

        assert hex_grid.position_of(eid) == (0, 0)
        assert eid in hex_grid.at(0, 0)

    def test_place_at_max_coordinates(self):
        hex_grid = HexGrid(width=10, height=10)
        eid = 1
        hex_grid.place(eid, 9, 9)

        assert hex_grid.position_of(eid) == (9, 9)
        assert eid in hex_grid.at(9, 9)

    def test_place_out_of_bounds_raises_value_error(self):
        hex_grid = HexGrid(width=10, height=10)

        with pytest.raises(ValueError):
            hex_grid.place(1, -1, 5)

        with pytest.raises(ValueError):
            hex_grid.place(1, 5, -1)

        with pytest.raises(ValueError):
            hex_grid.place(1, 10, 5)

        with pytest.raises(ValueError):
            hex_grid.place(1, 5, 10)

    def test_place_auto_removes_from_old_position(self):
        hex_grid = HexGrid(width=10, height=10)
        eid = 1

        hex_grid.place(eid, 3, 3)
        hex_grid.place(eid, 7, 7)

        assert eid not in hex_grid.at(3, 3)
        assert eid in hex_grid.at(7, 7)


class TestHexGridNeighbors:
    """Test hex neighbor topology."""

    def test_neighbors_center_has_six(self):
        hex_grid = HexGrid(width=10, height=10)
        neighbors = hex_grid.neighbors(5, 5)

        # Hex directions: (+1,0), (-1,0), (0,+1), (0,-1), (+1,-1), (-1,+1)
        expected = [
            (6, 5),   # +1, 0
            (4, 5),   # -1, 0
            (5, 6),   # 0, +1
            (5, 4),   # 0, -1
            (6, 4),   # +1, -1
            (4, 6),   # -1, +1
        ]

        assert len(neighbors) == 6
        for coord in expected:
            assert coord in neighbors

    def test_neighbors_corner_zero_zero_within_bounds(self):
        hex_grid = HexGrid(width=10, height=10)
        neighbors = hex_grid.neighbors(0, 0)

        # Only neighbors within bounds
        # From (0,0): (+1,0)=(1,0), (0,+1)=(0,1)
        # (-1,0)=(-1,0) OOB, (0,-1)=(0,-1) OOB
        # (+1,-1)=(1,-1) OOB, (-1,+1)=(-1,1) OOB

        valid_neighbors = []
        for coord in neighbors:
            q, r = coord
            if 0 <= q < 10 and 0 <= r < 10:
                valid_neighbors.append(coord)

        # Should only have valid neighbors
        assert len(neighbors) == len(valid_neighbors)
        assert (1, 0) in neighbors
        assert (0, 1) in neighbors

    def test_neighbors_respects_bounds(self):
        hex_grid = HexGrid(width=5, height=5)
        neighbors = hex_grid.neighbors(0, 0)

        # All neighbors should be within [0,5) x [0,5)
        for q, r in neighbors:
            assert 0 <= q < 5
            assert 0 <= r < 5


class TestHexGridDistance:
    """Test hex distance calculations."""

    def test_hex_distance_same_point(self):
        hex_grid = HexGrid(width=10, height=10)
        distance = hex_grid.heuristic((5, 5), (5, 5))

        assert distance == 0

    def test_hex_distance_adjacent_cells(self):
        hex_grid = HexGrid(width=10, height=10)

        # Distance to each of the 6 neighbors should be 1
        distances = [
            hex_grid.heuristic((5, 5), (6, 5)),  # +1, 0
            hex_grid.heuristic((5, 5), (4, 5)),  # -1, 0
            hex_grid.heuristic((5, 5), (5, 6)),  # 0, +1
            hex_grid.heuristic((5, 5), (5, 4)),  # 0, -1
            hex_grid.heuristic((5, 5), (6, 4)),  # +1, -1
            hex_grid.heuristic((5, 5), (4, 6)),  # -1, +1
        ]

        for d in distances:
            assert d == 1

    def test_hex_distance_formula(self):
        hex_grid = HexGrid(width=10, height=10)

        # Hex distance: (abs(dq) + abs(dq + dr) + abs(dr)) // 2
        # From (0,0) to (2,3):
        # dq = 2, dr = 3
        # distance = (abs(2) + abs(2+3) + abs(3)) // 2 = (2 + 5 + 3) // 2 = 5
        distance = hex_grid.heuristic((0, 0), (2, 3))

        assert distance == 5

    def test_hex_distance_symmetric(self):
        hex_grid = HexGrid(width=10, height=10)

        d1 = hex_grid.heuristic((1, 2), (5, 7))
        d2 = hex_grid.heuristic((5, 7), (1, 2))

        assert d1 == d2

    def test_hex_distance_known_value(self):
        hex_grid = HexGrid(width=10, height=10)

        # From (1,1) to (4,5):
        # dq = 3, dr = 4
        # distance = (abs(3) + abs(3+4) + abs(4)) // 2 = (3 + 7 + 4) // 2 = 7
        distance = hex_grid.heuristic((1, 1), (4, 5))

        assert distance == 7


class TestHexGridRadiusQueries:
    """Test radius queries using hex distance."""

    def test_in_radius_zero_returns_only_center(self):
        hex_grid = HexGrid(width=10, height=10)
        eid = 1
        hex_grid.place(eid, 5, 5)

        results = hex_grid.in_radius(5, 5, 0)

        assert len(results) == 1
        assert (eid, 5, 5) in results

    def test_in_radius_one_returns_neighbors(self):
        hex_grid = HexGrid(width=10, height=10)

        # Place entity at center
        center_eid = 100
        hex_grid.place(center_eid, 5, 5)

        # Place entities at all 6 neighbors
        neighbor_offsets = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
        neighbor_eids = []
        for i, (dq, dr) in enumerate(neighbor_offsets):
            eid = i + 1
            neighbor_eids.append(eid)
            hex_grid.place(eid, 5 + dq, 5 + dr)

        results = hex_grid.in_radius(5, 5, 1)

        # Should return center + 6 neighbors = 7
        assert len(results) == 7

        found_eids = [r[0] for r in results]
        assert center_eid in found_eids
        for eid in neighbor_eids:
            assert eid in found_eids

    def test_in_radius_excludes_beyond_radius(self):
        hex_grid = HexGrid(width=10, height=10)

        eid_near = 1
        eid_far = 2

        hex_grid.place(eid_near, 6, 5)  # Hex distance 1
        hex_grid.place(eid_far, 8, 5)   # Hex distance > 1

        results = hex_grid.in_radius(5, 5, 1)

        assert any(r[0] == eid_near for r in results)
        assert not any(r[0] == eid_far for r in results)


class TestHexGridRebuild:
    """Test world rebuild functionality."""

    def test_rebuild_places_entities_from_world(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        hex_grid = HexGrid(width=10, height=10)

        world.register_component(Pos2D)

        eid1 = world.spawn()
        eid2 = world.spawn()
        world.attach(eid1, Pos2D(x=3, y=4))
        world.attach(eid2, Pos2D(x=7, y=2))

        hex_grid.rebuild(world)

        assert hex_grid.position_of(eid1) == (3, 4)
        assert hex_grid.position_of(eid2) == (7, 2)

    def test_rebuild_discretizes_float_coordinates(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        hex_grid = HexGrid(width=10, height=10)

        world.register_component(Pos2D)

        eid = world.spawn()
        world.attach(eid, Pos2D(x=3.7, y=2.1))

        hex_grid.rebuild(world)

        # Should discretize to (3, 2)
        assert hex_grid.position_of(eid) == (3, 2)

    def test_rebuild_skips_out_of_bounds_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        hex_grid = HexGrid(width=10, height=10)

        world.register_component(Pos2D)

        eid_oob = world.spawn()
        eid_valid = world.spawn()
        world.attach(eid_oob, Pos2D(x=-1, y=0))
        world.attach(eid_valid, Pos2D(x=5, y=5))

        # Should not raise, silently skip OOB entity
        hex_grid.rebuild(world)

        assert hex_grid.position_of(eid_oob) is None
        assert hex_grid.position_of(eid_valid) == (5, 5)

    def test_rebuild_clears_existing_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        hex_grid = HexGrid(width=10, height=10)

        world.register_component(Pos2D)

        # Place entity manually
        hex_grid.place(999, 5, 5)

        # Rebuild from empty world
        hex_grid.rebuild(world)

        # Manual placement should be cleared
        assert hex_grid.position_of(999) is None
