"""Tests for tick_colony.grid module - spatial primitives."""

import pytest
from tick_colony import Grid, Position, make_grid_cleanup_system
from tick import Engine


class TestPosition:
    def test_position_creation(self):
        pos = Position(x=5, y=10)
        assert pos.x == 5
        assert pos.y == 10

    def test_position_mutable(self):
        pos = Position(x=1, y=2)
        pos.x = 3
        pos.y = 4
        assert pos.x == 3
        assert pos.y == 4


class TestGrid:
    def test_grid_construction(self):
        grid = Grid(30, 20)
        assert grid.width == 30
        assert grid.height == 20

    def test_place_entity(self):
        grid = Grid(10, 10)
        grid.place(1, 5, 5)
        assert grid.position_of(1) == (5, 5)
        assert 1 in grid.at(5, 5)

    def test_place_out_of_bounds_raises_error(self):
        grid = Grid(10, 10)
        with pytest.raises(ValueError, match="out of bounds"):
            grid.place(1, 10, 5)
        with pytest.raises(ValueError, match="out of bounds"):
            grid.place(1, 5, 10)
        with pytest.raises(ValueError, match="out of bounds"):
            grid.place(1, -1, 5)

    def test_move_entity(self):
        grid = Grid(10, 10)
        grid.place(1, 2, 2)
        grid.move(1, 3, 4)
        assert grid.position_of(1) == (3, 4)
        assert 1 not in grid.at(2, 2)
        assert 1 in grid.at(3, 4)

    def test_move_nonexistent_entity_raises_error(self):
        grid = Grid(10, 10)
        with pytest.raises(KeyError):
            grid.move(999, 5, 5)

    def test_move_out_of_bounds_raises_error(self):
        grid = Grid(10, 10)
        grid.place(1, 5, 5)
        with pytest.raises(ValueError, match="out of bounds"):
            grid.move(1, 10, 5)

    def test_remove_entity(self):
        grid = Grid(10, 10)
        grid.place(1, 5, 5)
        grid.remove(1)
        assert grid.position_of(1) is None
        assert 1 not in grid.at(5, 5)

    def test_remove_nonexistent_entity_noop(self):
        grid = Grid(10, 10)
        grid.remove(999)  # Should not raise

    def test_at_returns_frozenset(self):
        grid = Grid(10, 10)
        grid.place(1, 5, 5)
        grid.place(2, 5, 5)
        entities = grid.at(5, 5)
        assert isinstance(entities, frozenset)
        assert entities == frozenset([1, 2])

    def test_at_empty_tile(self):
        grid = Grid(10, 10)
        entities = grid.at(5, 5)
        assert entities == frozenset()

    def test_position_of_nonexistent_entity(self):
        grid = Grid(10, 10)
        assert grid.position_of(999) is None

    def test_in_radius_chebyshev_distance(self):
        grid = Grid(20, 20)
        grid.place(1, 10, 10)
        grid.place(2, 11, 10)
        grid.place(3, 12, 12)
        grid.place(4, 15, 15)

        results = grid.in_radius(10, 10, 1)
        eids = [eid for eid, x, y in results]
        assert 1 in eids
        assert 2 in eids
        assert 3 not in eids

        results = grid.in_radius(10, 10, 2)
        eids = [eid for eid, x, y in results]
        assert 1 in eids
        assert 2 in eids
        assert 3 in eids
        assert 4 not in eids

    def test_in_radius_returns_positions(self):
        grid = Grid(20, 20)
        grid.place(1, 5, 5)
        grid.place(2, 6, 6)

        results = grid.in_radius(5, 5, 2)
        assert (1, 5, 5) in results
        assert (2, 6, 6) in results

    def test_neighbors_with_diagonals(self):
        grid = Grid(10, 10)
        neighbors = grid.neighbors(5, 5, diagonal=True)
        assert len(neighbors) == 8
        assert (4, 4) in neighbors
        assert (4, 5) in neighbors
        assert (4, 6) in neighbors
        assert (5, 4) in neighbors
        assert (5, 6) in neighbors
        assert (6, 4) in neighbors
        assert (6, 5) in neighbors
        assert (6, 6) in neighbors

    def test_neighbors_without_diagonals(self):
        grid = Grid(10, 10)
        neighbors = grid.neighbors(5, 5, diagonal=False)
        assert len(neighbors) == 4
        assert (4, 5) in neighbors
        assert (6, 5) in neighbors
        assert (5, 4) in neighbors
        assert (5, 6) in neighbors

    def test_neighbors_at_edge(self):
        grid = Grid(10, 10)
        neighbors = grid.neighbors(0, 0, diagonal=True)
        assert len(neighbors) == 3
        assert (0, 1) in neighbors
        assert (1, 0) in neighbors
        assert (1, 1) in neighbors

    def test_neighbors_at_corner_without_diagonals(self):
        grid = Grid(10, 10)
        neighbors = grid.neighbors(9, 9, diagonal=False)
        assert len(neighbors) == 2
        assert (8, 9) in neighbors
        assert (9, 8) in neighbors

    def test_pathfind_simple_path(self):
        grid = Grid(10, 10)
        path = grid.pathfind((0, 0), (3, 0))
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (3, 0)
        assert len(path) == 4

    def test_pathfind_diagonal_path(self):
        grid = Grid(10, 10)
        path = grid.pathfind((0, 0), (2, 2))
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (2, 2)
        assert len(path) == 3  # Diagonal movement

    def test_pathfind_with_blocked_path(self):
        grid = Grid(10, 10)

        # Block column x=5 except at y=0 (start) and y=9 (goal)
        def passable(x, y):
            if x == 5 and 1 <= y <= 8:
                return False
            return True

        path = grid.pathfind((5, 0), (5, 9), passable=passable)
        assert path is not None
        assert path[0] == (5, 0)
        assert path[-1] == (5, 9)
        # Path must go around the blocked column
        for x, y in path[1:-1]:
            if x == 5:
                assert y < 1 or y > 8

    def test_pathfind_no_path_available(self):
        grid = Grid(10, 10)

        def passable(x, y):
            # Block everything above y=5
            return y <= 4

        path = grid.pathfind((2, 2), (7, 7), passable=passable)
        assert path is None

    def test_pathfind_start_equals_goal(self):
        grid = Grid(10, 10)
        path = grid.pathfind((5, 5), (5, 5))
        assert path == [(5, 5)]

    def test_pathfind_default_all_passable(self):
        grid = Grid(20, 20)
        path = grid.pathfind((0, 0), (19, 19))
        assert path is not None
        assert len(path) == 20  # Diagonal is optimal

    def test_rebuild_from_world_positions(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid(10, 10)

        e1 = world.spawn()
        world.attach(e1, Position(x=2, y=3))
        e2 = world.spawn()
        world.attach(e2, Position(x=4, y=5))
        e3 = world.spawn()
        world.attach(e3, Position(x=2, y=3))  # Same position as e1

        grid.rebuild(world)

        assert grid.position_of(e1) == (2, 3)
        assert grid.position_of(e2) == (4, 5)
        assert grid.position_of(e3) == (2, 3)
        assert e1 in grid.at(2, 3)
        assert e3 in grid.at(2, 3)
        assert e2 in grid.at(4, 5)

    def test_rebuild_clears_existing_data(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid(10, 10)

        grid.place(999, 5, 5)
        assert grid.position_of(999) == (5, 5)

        e1 = world.spawn()
        world.attach(e1, Position(x=1, y=1))

        grid.rebuild(world)

        assert grid.position_of(999) is None
        assert grid.position_of(e1) == (1, 1)


class TestGridCleanupSystem:
    def test_cleanup_system_removes_dead_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid(10, 10)

        e1 = world.spawn()
        e2 = world.spawn()
        grid.place(e1, 5, 5)
        grid.place(e2, 6, 6)

        world.despawn(e1)

        cleanup_system = make_grid_cleanup_system(grid)
        engine.add_system(cleanup_system)
        engine.step()

        assert grid.position_of(e1) is None
        assert grid.position_of(e2) == (6, 6)

    def test_cleanup_system_multiple_dead_entities(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world
        grid = Grid(10, 10)

        entities = [world.spawn() for _ in range(5)]
        for i, e in enumerate(entities):
            grid.place(e, i, i)

        world.despawn(entities[1])
        world.despawn(entities[3])

        cleanup_system = make_grid_cleanup_system(grid)
        engine.add_system(cleanup_system)
        engine.step()

        assert grid.position_of(entities[0]) == (0, 0)
        assert grid.position_of(entities[1]) is None
        assert grid.position_of(entities[2]) == (2, 2)
        assert grid.position_of(entities[3]) is None
        assert grid.position_of(entities[4]) == (4, 4)
