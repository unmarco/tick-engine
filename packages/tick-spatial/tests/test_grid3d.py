"""
Test suite for Grid3D spatial indexing.

Tests cover:
- Constructor and properties
- Entity placement and retrieval
- Bounds checking
- Movement operations
- Removal operations
- Multi-entity cells
- Neighbor queries (26-directional)
- Radius queries (3D Chebyshev distance)
- Heuristic calculations
- World rebuild functionality
"""

import pytest
from tick_spatial import Pos3D, Grid3D, make_spatial_cleanup_system
from tick import Engine


class TestGrid3DConstruction:
    """Test Grid3D initialization and properties."""

    def test_constructor_sets_dimensions(self):
        grid = Grid3D(width=10, height=10, depth=10)
        assert grid.width == 10
        assert grid.height == 10
        assert grid.depth == 10

    def test_constructor_different_dimensions(self):
        grid = Grid3D(width=20, height=15, depth=8)
        assert grid.width == 20
        assert grid.height == 15
        assert grid.depth == 8


class TestGrid3DPlacement:
    """Test entity placement operations."""

    def test_place_and_retrieve_entity(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1
        grid.place(eid, (5, 5, 5))

        entities = grid.at((5, 5, 5))
        assert eid in entities
        assert grid.position_of(eid) == (5, 5, 5)

    def test_place_at_zero_zero_zero(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1
        grid.place(eid, (0, 0, 0))

        assert grid.position_of(eid) == (0, 0, 0)
        assert eid in grid.at((0, 0, 0))

    def test_place_at_max_coordinates(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1
        grid.place(eid, (9, 9, 9))

        assert grid.position_of(eid) == (9, 9, 9)
        assert eid in grid.at((9, 9, 9))

    def test_place_negative_x_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (-1, 5, 5))

    def test_place_negative_y_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (5, -1, 5))

    def test_place_negative_z_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (5, 5, -1))

    def test_place_x_at_width_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (10, 5, 5))

    def test_place_y_at_height_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (5, 10, 5))

    def test_place_z_at_depth_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (5, 5, 10))

    def test_place_beyond_bounds_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        with pytest.raises(ValueError):
            grid.place(1, (15, 15, 15))

    def test_place_auto_removes_from_old_position(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1

        grid.place(eid, (3, 3, 3))
        assert eid in grid.at((3, 3, 3))

        grid.place(eid, (7, 7, 7))
        assert eid not in grid.at((3, 3, 3))
        assert eid in grid.at((7, 7, 7))
        assert grid.position_of(eid) == (7, 7, 7)


class TestGrid3DMovement:
    """Test entity movement operations."""

    def test_move_updates_position(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1

        grid.place(eid, (2, 2, 2))
        grid.move(eid, (6, 6, 6))

        assert grid.position_of(eid) == (6, 6, 6)
        assert eid in grid.at((6, 6, 6))
        assert eid not in grid.at((2, 2, 2))

    def test_move_out_of_bounds_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1
        grid.place(eid, (5, 5, 5))

        with pytest.raises(ValueError):
            grid.move(eid, (10, 5, 5))

    def test_move_to_negative_raises_value_error(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1
        grid.place(eid, (5, 5, 5))

        with pytest.raises(ValueError):
            grid.move(eid, (-1, 5, 5))

    def test_move_entity_not_on_grid_raises_key_error(self):
        grid = Grid3D(width=10, height=10, depth=10)

        with pytest.raises(KeyError):
            grid.move(999, (5, 5, 5))


class TestGrid3DRemoval:
    """Test entity removal operations."""

    def test_remove_entity(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1

        grid.place(eid, (4, 4, 4))
        grid.remove(eid)

        assert grid.position_of(eid) is None
        assert eid not in grid.at((4, 4, 4))

    def test_remove_entity_not_on_grid_is_noop(self):
        grid = Grid3D(width=10, height=10, depth=10)
        # Should not raise
        grid.remove(999)


class TestGrid3DMultipleEntities:
    """Test handling of multiple entities."""

    def test_at_empty_cell_returns_empty_frozenset(self):
        grid = Grid3D(width=10, height=10, depth=10)
        entities = grid.at((5, 5, 5))

        assert isinstance(entities, frozenset)
        assert len(entities) == 0

    def test_multiple_entities_at_same_cell(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid1 = 1
        eid2 = 2

        grid.place(eid1, (5, 5, 5))
        grid.place(eid2, (5, 5, 5))

        entities = grid.at((5, 5, 5))
        assert eid1 in entities
        assert eid2 in entities
        assert len(entities) == 2


class TestGrid3DNeighbors:
    """Test neighbor queries (26-directional)."""

    def test_neighbors_center_has_twenty_six(self):
        grid = Grid3D(width=10, height=10, depth=10)
        neighbors = grid.neighbors((5, 5, 5))

        # 3x3x3 cube minus center = 27 - 1 = 26
        assert len(neighbors) == 26

        # Verify all neighbors are within 1 step in all dimensions
        for nx, ny, nz in neighbors:
            assert abs(nx - 5) <= 1
            assert abs(ny - 5) <= 1
            assert abs(nz - 5) <= 1
            # Ensure it's not the center itself
            assert (nx, ny, nz) != (5, 5, 5)

    def test_neighbors_corner_zero_zero_zero_has_seven(self):
        grid = Grid3D(width=10, height=10, depth=10)
        neighbors = grid.neighbors((0, 0, 0))

        # Corner: only positive directions available
        # (1,0,0), (0,1,0), (0,0,1), (1,1,0), (1,0,1), (0,1,1), (1,1,1)
        assert len(neighbors) == 7

        # All neighbors should have positive coordinates
        for nx, ny, nz in neighbors:
            assert nx >= 0 and ny >= 0 and nz >= 0
            assert 0 <= nx <= 1 and 0 <= ny <= 1 and 0 <= nz <= 1
            assert (nx, ny, nz) != (0, 0, 0)

    def test_neighbors_edge_cell(self):
        grid = Grid3D(width=10, height=10, depth=10)
        # Edge: x=0, but y and z are interior
        neighbors = grid.neighbors((0, 5, 5))

        # One face constrained: 3x3x3 - half = fewer neighbors
        # x can only be 0 or 1 (2 values)
        # y can be 4, 5, 6 (3 values)
        # z can be 4, 5, 6 (3 values)
        # Total: 2*3*3 - 1 (center) = 17
        assert len(neighbors) == 17

    def test_neighbors_face_cell(self):
        grid = Grid3D(width=10, height=10, depth=10)
        # Face cell: on one face but not on edges
        neighbors = grid.neighbors((5, 5, 0))

        # z=0 constrains to z in {0, 1}
        # x in {4, 5, 6}, y in {4, 5, 6}, z in {0, 1}
        # Total: 3*3*2 - 1 = 17
        assert len(neighbors) == 17

    def test_neighbors_small_grid(self):
        grid = Grid3D(width=2, height=2, depth=2)
        # 2x2x2 grid: 8 cells total
        neighbors = grid.neighbors((0, 0, 0))

        # All other cells are neighbors
        assert len(neighbors) == 7

        expected = [
            (1, 0, 0), (0, 1, 0), (0, 0, 1),
            (1, 1, 0), (1, 0, 1), (0, 1, 1),
            (1, 1, 1),
        ]
        for coord in expected:
            assert coord in neighbors


class TestGrid3DRadiusQueries:
    """Test radius queries using 3D Chebyshev distance."""

    def test_in_radius_zero_returns_only_center(self):
        grid = Grid3D(width=10, height=10, depth=10)
        eid = 1
        grid.place(eid, (5, 5, 5))

        results = grid.in_radius((5, 5, 5), 0)

        assert len(results) == 1
        assert (eid, (5, 5, 5)) in results

    def test_in_radius_one_returns_3x3x3_neighborhood(self):
        grid = Grid3D(width=10, height=10, depth=10)

        # Place entities in a 3x3x3 cube
        eids = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                for dz in range(-1, 2):
                    eid = (dx + 1) * 9 + (dy + 1) * 3 + (dz + 1)
                    eids.append(eid)
                    grid.place(eid, (5 + dx, 5 + dy, 5 + dz))

        results = grid.in_radius((5, 5, 5), 1)

        # 3x3x3 = 27 entities
        assert len(results) == 27
        for eid in eids:
            found = any(r[0] == eid for r in results)
            assert found

    def test_in_radius_excludes_beyond_radius(self):
        grid = Grid3D(width=10, height=10, depth=10)

        eid_near = 1
        eid_far = 2

        grid.place(eid_near, (6, 5, 5))  # Distance 1
        grid.place(eid_far, (8, 8, 8))   # Distance 3 (max of |8-5|, |8-5|, |8-5|)

        results = grid.in_radius((5, 5, 5), 1)

        assert any(r[0] == eid_near for r in results)
        assert not any(r[0] == eid_far for r in results)

    def test_in_radius_empty_grid(self):
        grid = Grid3D(width=10, height=10, depth=10)
        results = grid.in_radius((5, 5, 5), 2)

        assert len(results) == 0


class TestGrid3DHeuristic:
    """Test 3D Chebyshev distance heuristic."""

    def test_heuristic_same_point(self):
        grid = Grid3D(width=10, height=10, depth=10)
        distance = grid.heuristic((5, 5, 5), (5, 5, 5))

        assert distance == 0

    def test_heuristic_along_x_axis(self):
        grid = Grid3D(width=10, height=10, depth=10)
        distance = grid.heuristic((0, 0, 0), (5, 0, 0))

        assert distance == 5

    def test_heuristic_along_y_axis(self):
        grid = Grid3D(width=10, height=10, depth=10)
        distance = grid.heuristic((0, 0, 0), (0, 5, 0))

        assert distance == 5

    def test_heuristic_along_z_axis(self):
        grid = Grid3D(width=10, height=10, depth=10)
        distance = grid.heuristic((0, 0, 0), (0, 0, 5))

        assert distance == 5

    def test_heuristic_diagonal_is_max_component(self):
        grid = Grid3D(width=10, height=10, depth=10)
        # Chebyshev distance: max(|dx|, |dy|, |dz|)
        distance = grid.heuristic((0, 0, 0), (3, 3, 3))

        assert distance == 3

    def test_heuristic_mixed_diagonal(self):
        grid = Grid3D(width=10, height=10, depth=10)
        # max(|5-0|, |3-0|, |2-0|) = max(5, 3, 2) = 5
        distance = grid.heuristic((0, 0, 0), (5, 3, 2))

        assert distance == 5

    def test_heuristic_symmetric(self):
        grid = Grid3D(width=10, height=10, depth=10)
        d1 = grid.heuristic((1, 2, 3), (8, 7, 4))
        d2 = grid.heuristic((8, 7, 4), (1, 2, 3))

        assert d1 == d2


class TestGrid3DRebuild:
    """Test world rebuild functionality."""

    def test_rebuild_places_entities_from_world(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid3D(width=10, height=10, depth=10)

        world.register_component(Pos3D)

        eid1 = world.spawn()
        eid2 = world.spawn()
        world.attach(eid1, Pos3D(x=3, y=4, z=2))
        world.attach(eid2, Pos3D(x=7, y=2, z=8))

        grid.rebuild(world)

        assert grid.position_of(eid1) == (3, 4, 2)
        assert grid.position_of(eid2) == (7, 2, 8)

    def test_rebuild_discretizes_float_coordinates(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid3D(width=10, height=10, depth=10)

        world.register_component(Pos3D)

        eid = world.spawn()
        world.attach(eid, Pos3D(x=3.7, y=2.1, z=5.9))

        grid.rebuild(world)

        # Should discretize to (3, 2, 5)
        assert grid.position_of(eid) == (3, 2, 5)

    def test_rebuild_skips_out_of_bounds_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid3D(width=10, height=10, depth=10)

        world.register_component(Pos3D)

        eid_oob = world.spawn()
        eid_valid = world.spawn()
        world.attach(eid_oob, Pos3D(x=-1, y=0, z=0))
        world.attach(eid_valid, Pos3D(x=5, y=5, z=5))

        # Should not raise, silently skip OOB entity
        grid.rebuild(world)

        assert grid.position_of(eid_oob) is None
        assert grid.position_of(eid_valid) == (5, 5, 5)


class TestGrid3DCleanupSystem:
    """Test spatial cleanup system integration."""

    def test_despawned_entity_removed_from_grid(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid3D(width=10, height=10, depth=10)

        world.register_component(Pos3D)
        cleanup_system = make_spatial_cleanup_system(grid)
        engine.add_system(cleanup_system)

        eid = world.spawn()
        world.attach(eid, Pos3D(x=5, y=5, z=5))
        grid.place(eid, (5, 5, 5))

        world.despawn(eid)
        engine.step()

        assert grid.position_of(eid) is None

    def test_alive_entities_kept_in_grid(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid3D(width=10, height=10, depth=10)

        world.register_component(Pos3D)
        cleanup_system = make_spatial_cleanup_system(grid)
        engine.add_system(cleanup_system)

        eid = world.spawn()
        world.attach(eid, Pos3D(x=5, y=5, z=5))
        grid.place(eid, (5, 5, 5))

        engine.step()

        # Entity still alive, should remain
        assert grid.position_of(eid) == (5, 5, 5)
