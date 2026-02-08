"""
Test suite for Grid2D spatial indexing.

Tests cover:
- Constructor and properties
- Entity placement and retrieval
- Bounds checking
- Movement operations
- Removal operations
- Multi-entity cells
- Neighbor queries
- Radius queries (Chebyshev distance)
- Heuristic calculations
- World rebuild functionality
"""

import pytest
from tick_spatial import Pos2D, Grid2D, make_spatial_cleanup_system
from tick import Engine


class TestGrid2DConstruction:
    """Test Grid2D initialization and properties."""

    def test_constructor_sets_dimensions(self):
        grid = Grid2D(width=10, height=10)
        assert grid.width == 10
        assert grid.height == 10

    def test_constructor_different_dimensions(self):
        grid = Grid2D(width=20, height=15)
        assert grid.width == 20
        assert grid.height == 15


class TestGrid2DPlacement:
    """Test entity placement operations."""

    def test_place_and_retrieve_entity(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 5, 5)

        entities = grid.at(5, 5)
        assert eid in entities
        assert grid.position_of(eid) == (5, 5)

    def test_place_at_zero_zero(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 0, 0)

        assert grid.position_of(eid) == (0, 0)
        assert eid in grid.at(0, 0)

    def test_place_at_max_coordinates(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 9, 9)

        assert grid.position_of(eid) == (9, 9)
        assert eid in grid.at(9, 9)

    def test_place_negative_x_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        with pytest.raises(ValueError):
            grid.place(1, -1, 5)

    def test_place_negative_y_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        with pytest.raises(ValueError):
            grid.place(1, 5, -1)

    def test_place_x_at_width_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        with pytest.raises(ValueError):
            grid.place(1, 10, 5)

    def test_place_y_at_height_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        with pytest.raises(ValueError):
            grid.place(1, 5, 10)

    def test_place_x_beyond_width_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        with pytest.raises(ValueError):
            grid.place(1, 15, 5)

    def test_place_auto_removes_from_old_position(self):
        grid = Grid2D(width=10, height=10)
        eid = 1

        grid.place(eid, 3, 3)
        assert eid in grid.at(3, 3)

        grid.place(eid, 7, 7)
        assert eid not in grid.at(3, 3)
        assert eid in grid.at(7, 7)
        assert grid.position_of(eid) == (7, 7)


class TestGrid2DMovement:
    """Test entity movement operations."""

    def test_move_updates_position(self):
        grid = Grid2D(width=10, height=10)
        eid = 1

        grid.place(eid, 2, 2)
        grid.move(eid, 6, 6)

        assert grid.position_of(eid) == (6, 6)
        assert eid in grid.at(6, 6)
        assert eid not in grid.at(2, 2)

    def test_move_out_of_bounds_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 5, 5)

        with pytest.raises(ValueError):
            grid.move(eid, 10, 5)

    def test_move_to_negative_raises_value_error(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 5, 5)

        with pytest.raises(ValueError):
            grid.move(eid, -1, 5)

    def test_move_entity_not_on_grid_raises_key_error(self):
        grid = Grid2D(width=10, height=10)

        with pytest.raises(KeyError):
            grid.move(999, 5, 5)


class TestGrid2DRemoval:
    """Test entity removal operations."""

    def test_remove_entity(self):
        grid = Grid2D(width=10, height=10)
        eid = 1

        grid.place(eid, 4, 4)
        grid.remove(eid)

        assert grid.position_of(eid) is None
        assert eid not in grid.at(4, 4)

    def test_remove_entity_not_on_grid_is_noop(self):
        grid = Grid2D(width=10, height=10)
        # Should not raise
        grid.remove(999)


class TestGrid2DMultipleEntities:
    """Test handling of multiple entities."""

    def test_at_empty_cell_returns_empty_frozenset(self):
        grid = Grid2D(width=10, height=10)
        entities = grid.at(5, 5)

        assert isinstance(entities, frozenset)
        assert len(entities) == 0

    def test_multiple_entities_at_same_cell(self):
        grid = Grid2D(width=10, height=10)
        eid1 = 1
        eid2 = 2

        grid.place(eid1, 5, 5)
        grid.place(eid2, 5, 5)

        entities = grid.at(5, 5)
        assert eid1 in entities
        assert eid2 in entities
        assert len(entities) == 2


class TestGrid2DNeighbors:
    """Test neighbor queries."""

    def test_neighbors_center_has_eight(self):
        grid = Grid2D(width=10, height=10)
        neighbors = grid.neighbors(5, 5)

        expected = [
            (4, 4), (5, 4), (6, 4),
            (4, 5),         (6, 5),
            (4, 6), (5, 6), (6, 6),
        ]

        assert len(neighbors) == 8
        for coord in expected:
            assert coord in neighbors

    def test_neighbors_corner_zero_zero_has_three(self):
        grid = Grid2D(width=10, height=10)
        neighbors = grid.neighbors(0, 0)

        expected = [(1, 0), (0, 1), (1, 1)]

        assert len(neighbors) == 3
        for coord in expected:
            assert coord in neighbors

    def test_neighbors_corner_max_max_has_three(self):
        grid = Grid2D(width=10, height=10)
        neighbors = grid.neighbors(9, 9)

        expected = [(8, 8), (9, 8), (8, 9)]

        assert len(neighbors) == 3
        for coord in expected:
            assert coord in neighbors

    def test_neighbors_edge_has_five(self):
        grid = Grid2D(width=10, height=10)
        neighbors = grid.neighbors(0, 5)

        expected = [
            (0, 4), (1, 4),
            (1, 5),
            (0, 6), (1, 6),
        ]

        assert len(neighbors) == 5
        for coord in expected:
            assert coord in neighbors

    def test_neighbors_top_edge(self):
        grid = Grid2D(width=10, height=10)
        neighbors = grid.neighbors(5, 0)

        assert len(neighbors) == 5
        assert (4, 0) in neighbors
        assert (6, 0) in neighbors
        assert (4, 1) in neighbors
        assert (5, 1) in neighbors
        assert (6, 1) in neighbors


class TestGrid2DRadiusQueries:
    """Test radius queries using Chebyshev distance."""

    def test_in_radius_zero_returns_only_center(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 5, 5)

        results = grid.in_radius(5, 5, 0)

        assert len(results) == 1
        assert (eid, 5, 5) in results

    def test_in_radius_one_returns_neighbors(self):
        grid = Grid2D(width=10, height=10)

        # Place entities in a 3x3 grid
        eids = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                eid = (dx + 1) * 3 + (dy + 1)
                eids.append(eid)
                grid.place(eid, 5 + dx, 5 + dy)

        results = grid.in_radius(5, 5, 1)

        assert len(results) == 9
        for eid in eids:
            found = any(r[0] == eid for r in results)
            assert found

    def test_in_radius_chebyshev_diagonal(self):
        grid = Grid2D(width=10, height=10)

        # Entity at diagonal distance 1 (Chebyshev)
        eid = 1
        grid.place(eid, 6, 6)

        results = grid.in_radius(5, 5, 1)

        # Should be within radius 1
        assert any(r[0] == eid for r in results)

    def test_in_radius_excludes_beyond_radius(self):
        grid = Grid2D(width=10, height=10)

        eid_near = 1
        eid_far = 2

        grid.place(eid_near, 6, 5)  # Distance 1
        grid.place(eid_far, 8, 5)   # Distance 3

        results = grid.in_radius(5, 5, 1)

        assert any(r[0] == eid_near for r in results)
        assert not any(r[0] == eid_far for r in results)

    def test_in_radius_returns_coordinates(self):
        grid = Grid2D(width=10, height=10)
        eid = 1
        grid.place(eid, 6, 7)

        results = grid.in_radius(5, 5, 2)

        # Should return (eid, x, y) tuples
        assert (eid, 6, 7) in results

    def test_in_radius_empty_grid(self):
        grid = Grid2D(width=10, height=10)
        results = grid.in_radius(5, 5, 2)

        assert len(results) == 0


class TestGrid2DHeuristic:
    """Test Chebyshev distance heuristic."""

    def test_heuristic_same_point(self):
        grid = Grid2D(width=10, height=10)
        distance = grid.heuristic((5, 5), (5, 5))

        assert distance == 0

    def test_heuristic_horizontal(self):
        grid = Grid2D(width=10, height=10)
        distance = grid.heuristic((0, 0), (5, 0))

        assert distance == 5

    def test_heuristic_vertical(self):
        grid = Grid2D(width=10, height=10)
        distance = grid.heuristic((0, 0), (0, 5))

        assert distance == 5

    def test_heuristic_diagonal(self):
        grid = Grid2D(width=10, height=10)
        # Chebyshev distance: max(|dx|, |dy|)
        distance = grid.heuristic((0, 0), (3, 3))

        assert distance == 3

    def test_heuristic_mixed_diagonal(self):
        grid = Grid2D(width=10, height=10)
        # Chebyshev: max(|5-0|, |3-0|) = max(5, 3) = 5
        distance = grid.heuristic((0, 0), (5, 3))

        assert distance == 5

    def test_heuristic_symmetric(self):
        grid = Grid2D(width=10, height=10)
        d1 = grid.heuristic((1, 2), (8, 7))
        d2 = grid.heuristic((8, 7), (1, 2))

        assert d1 == d2


class TestGrid2DRebuild:
    """Test world rebuild functionality."""

    def test_rebuild_places_entities_from_world(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)

        eid1 = world.spawn()
        eid2 = world.spawn()
        world.attach(eid1, Pos2D(x=3, y=4))
        world.attach(eid2, Pos2D(x=7, y=2))

        grid.rebuild(world)

        assert grid.position_of(eid1) == (3, 4)
        assert grid.position_of(eid2) == (7, 2)

    def test_rebuild_discretizes_float_coordinates(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)

        eid = world.spawn()
        world.attach(eid, Pos2D(x=3.7, y=2.1))

        grid.rebuild(world)

        # Should discretize to (3, 2)
        assert grid.position_of(eid) == (3, 2)

    def test_rebuild_discretizes_multiple_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)

        eid1 = world.spawn()
        eid2 = world.spawn()
        world.attach(eid1, Pos2D(x=3.9, y=2.1))
        world.attach(eid2, Pos2D(x=3.1, y=2.9))

        grid.rebuild(world)

        assert grid.position_of(eid1) == (3, 2)
        assert grid.position_of(eid2) == (3, 2)
        # Both should be at the same cell
        assert eid1 in grid.at(3, 2)
        assert eid2 in grid.at(3, 2)

    def test_rebuild_skips_out_of_bounds_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)

        eid_oob = world.spawn()
        eid_valid = world.spawn()
        world.attach(eid_oob, Pos2D(x=-1, y=0))
        world.attach(eid_valid, Pos2D(x=5, y=5))

        # Should not raise, silently skip OOB entity
        grid.rebuild(world)

        assert grid.position_of(eid_oob) is None
        assert grid.position_of(eid_valid) == (5, 5)

    def test_rebuild_skips_entity_beyond_bounds(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)

        eid = world.spawn()
        world.attach(eid, Pos2D(x=15, y=5))

        grid.rebuild(world)

        assert grid.position_of(eid) is None

    def test_rebuild_clears_existing_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)

        # Place entity manually
        grid.place(999, 5, 5)

        # Rebuild from empty world
        grid.rebuild(world)

        # Manual placement should be cleared
        assert grid.position_of(999) is None


class TestGrid2DCleanupSystem:
    """Test spatial cleanup system integration."""

    def test_despawned_entity_removed_from_grid(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)
        cleanup_system = make_spatial_cleanup_system(grid)
        engine.add_system(cleanup_system)

        eid = world.spawn()
        world.attach(eid, Pos2D(x=5, y=5))
        grid.place(eid, 5, 5)

        world.despawn(eid)
        engine.step()

        assert grid.position_of(eid) is None

    def test_alive_entities_kept_in_grid(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)
        cleanup_system = make_spatial_cleanup_system(grid)
        engine.add_system(cleanup_system)

        eid = world.spawn()
        world.attach(eid, Pos2D(x=5, y=5))
        grid.place(eid, 5, 5)

        engine.step()

        # Entity still alive, should remain
        assert grid.position_of(eid) == (5, 5)

    def test_multiple_despawned_entities_cleaned_up(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid2D(width=10, height=10)

        world.register_component(Pos2D)
        cleanup_system = make_spatial_cleanup_system(grid)
        engine.add_system(cleanup_system)

        eids = []
        for i in range(5):
            eid = world.spawn()
            world.attach(eid, Pos2D(x=i, y=i))
            grid.place(eid, i, i)
            eids.append(eid)

        # Despawn all
        for eid in eids:
            world.despawn(eid)

        engine.step()

        # All should be removed
        for eid in eids:
            assert grid.position_of(eid) is None
