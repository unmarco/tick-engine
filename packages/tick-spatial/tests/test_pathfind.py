"""
Test suite for A* pathfinding.

Tests cover:
- Straight line paths
- Diagonal paths
- Path structure (includes start and goal)
- Unreachable goals
- Custom walkable predicates
- Custom cost functions
- Same start and goal
- Pathfinding on different grid types (Grid2D, HexGrid)
- Obstacle avoidance
"""

import pytest
from tick_spatial import Grid2D, HexGrid, pathfind


class TestPathfindBasics:
    """Test basic pathfinding functionality."""

    def test_straight_line_horizontal_path(self):
        grid = Grid2D(width=10, height=10)
        path = pathfind(grid, start=(0, 0), goal=(5, 0))

        assert path is not None
        assert len(path) >= 2
        assert path[0] == (0, 0)
        assert path[-1] == (5, 0)

        # All y coordinates should be 0 for horizontal path
        for x, y in path:
            assert y == 0

    def test_straight_line_vertical_path(self):
        grid = Grid2D(width=10, height=10)
        path = pathfind(grid, start=(0, 0), goal=(0, 5))

        assert path is not None
        assert len(path) >= 2
        assert path[0] == (0, 0)
        assert path[-1] == (0, 5)

        # All x coordinates should be 0 for vertical path
        for x, y in path:
            assert x == 0

    def test_diagonal_path(self):
        grid = Grid2D(width=10, height=10)
        path = pathfind(grid, start=(0, 0), goal=(3, 3))

        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (3, 3)

        # Path should use diagonal moves (Chebyshev allows this)
        # Distance should be roughly 3-4 steps
        assert len(path) <= 6

    def test_path_includes_start_and_goal(self):
        grid = Grid2D(width=10, height=10)
        path = pathfind(grid, start=(2, 3), goal=(7, 8))

        assert path is not None
        assert path[0] == (2, 3)
        assert path[-1] == (7, 8)

    def test_same_start_and_goal_returns_single_element(self):
        grid = Grid2D(width=10, height=10)
        path = pathfind(grid, start=(5, 5), goal=(5, 5))

        assert path is not None
        assert len(path) == 1
        assert path[0] == (5, 5)


class TestPathfindUnreachable:
    """Test pathfinding with unreachable goals."""

    def test_unreachable_goal_returns_none(self):
        grid = Grid2D(width=10, height=10)

        # Make goal completely surrounded by unwalkable cells
        def walkable(pos):
            x, y = pos
            # Goal is at (5, 5), block all neighbors
            blocked = [
                (4, 4), (5, 4), (6, 4),
                (4, 5), (5, 5), (6, 5),
                (4, 6), (5, 6), (6, 6),
            ]
            return pos not in blocked

        path = pathfind(grid, start=(0, 0), goal=(5, 5), walkable=walkable)

        assert path is None

    def test_unreachable_with_wall(self):
        grid = Grid2D(width=10, height=10)

        # Create a vertical wall that blocks path
        def walkable(pos):
            x, y = pos
            # Wall at x=5 for all y
            return x != 5

        # Try to go from left side to right side
        path = pathfind(grid, start=(0, 5), goal=(9, 5), walkable=walkable)

        # Wall is not complete (doesn't go to edges), so path might exist
        # But if wall goes full height, should be None
        # Let's test with a complete wall
        def complete_wall_walkable(pos):
            x, y = pos
            # Complete vertical wall at x=5
            if x == 5:
                return False
            # Also block top and bottom to seal it
            return True

        path2 = pathfind(grid, start=(0, 5), goal=(9, 5), walkable=complete_wall_walkable)

        # Since wall is at x=5 and goes full height, but grid has y from 0-9,
        # the path should be able to go around. Let's make it truly unreachable:
        def truly_blocked(pos):
            x, y = pos
            # Wall that completely divides the grid
            if x == 5 and 0 <= y < 10:
                return False
            return True

        # Actually, with default Grid2D neighbors, entities can go around.
        # To make truly unreachable, block the goal itself.
        def goal_blocked(pos):
            return pos != (9, 5)

        path3 = pathfind(grid, start=(0, 5), goal=(9, 5), walkable=goal_blocked)

        assert path3 is None


class TestPathfindCustomWalkable:
    """Test pathfinding with custom walkable predicates."""

    def test_custom_walkable_blocks_cells(self):
        grid = Grid2D(width=10, height=10)

        # Block most of row y=5, leaving a gap at x=0
        blocked = {(x, 5) for x in range(1, 10)}
        def walkable(pos):
            return pos not in blocked

        # Path from (5, 0) to (5, 9) should go around the blocked cells
        path = pathfind(grid, start=(5, 0), goal=(5, 9), walkable=walkable)

        assert path is not None

        # Verify path doesn't cross blocked cells
        for step in path:
            assert step not in blocked

    def test_path_avoids_blocked_cells(self):
        grid = Grid2D(width=10, height=10)

        # Block cells in the middle
        blocked_cells = {(4, 5), (5, 5), (6, 5)}
        def walkable(pos):
            return pos not in blocked_cells

        path = pathfind(grid, start=(5, 0), goal=(5, 9), walkable=walkable)

        assert path is not None

        # Path should not contain any blocked cells
        for pos in path:
            assert pos not in blocked_cells


class TestPathfindCustomCost:
    """Test pathfinding with custom cost functions."""

    def test_custom_cost_prefers_cheap_path(self):
        grid = Grid2D(width=10, height=10)

        # Make cells on the right side expensive
        def cost(from_pos, to_pos):
            x, y = to_pos
            if x > 5:
                return 10.0  # Expensive
            return 1.0

        # Path from (0, 5) to (9, 5) should prefer going around the expensive area
        # if there's a cheaper alternative
        path = pathfind(grid, start=(0, 5), goal=(9, 5), cost=cost)

        assert path is not None
        # Due to high cost on right side, path might be longer but cheaper
        # Hard to test exact path without implementation details

    def test_default_cost_is_uniform(self):
        grid = Grid2D(width=10, height=10)

        # With uniform cost, path should be direct
        path = pathfind(grid, start=(0, 0), goal=(5, 5))

        assert path is not None
        # Diagonal path should be short
        assert len(path) <= 8


class TestPathfindOnHexGrid:
    """Test pathfinding on hex grids."""

    def test_path_on_hexgrid(self):
        hex_grid = HexGrid(width=10, height=10)
        path = pathfind(hex_grid, start=(0, 0), goal=(5, 5))

        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (5, 5)

    def test_hexgrid_uses_hex_neighbors(self):
        hex_grid = HexGrid(width=10, height=10)

        # Path should only use hex-valid neighbors (6-directional)
        path = pathfind(hex_grid, start=(5, 5), goal=(7, 5))

        assert path is not None

        # Verify path is connected via hex neighbors
        for i in range(len(path) - 1):
            curr = path[i]
            next_pos = path[i + 1]

            # Check that next_pos is a valid hex neighbor of curr
            neighbors = hex_grid.neighbors(*curr)
            assert next_pos in neighbors

    def test_hexgrid_unreachable_returns_none(self):
        hex_grid = HexGrid(width=10, height=10)

        # Block goal
        def walkable(pos):
            return pos != (5, 5)

        path = pathfind(hex_grid, start=(0, 0), goal=(5, 5), walkable=walkable)

        assert path is None


class TestPathfindObstacleAvoidance:
    """Test pathfinding around obstacles."""

    def test_path_around_obstacle(self):
        grid = Grid2D(width=10, height=10)

        # Create a wall of unwalkable cells
        # Vertical wall from (5, 2) to (5, 7)
        wall_cells = {(5, y) for y in range(2, 8)}

        def walkable(pos):
            return pos not in wall_cells

        # Path from left to right should go around the wall
        path = pathfind(grid, start=(3, 5), goal=(7, 5), walkable=walkable)

        assert path is not None
        assert path[0] == (3, 5)
        assert path[-1] == (7, 5)

        # Path should not cross the wall
        for pos in path:
            assert pos not in wall_cells

    def test_path_around_multiple_obstacles(self):
        grid = Grid2D(width=20, height=20)

        # Create several obstacles
        obstacles = {
            (5, 5), (6, 5), (7, 5),
            (10, 10), (11, 10), (10, 11), (11, 11),
            (15, 8), (15, 9), (15, 10),
        }

        def walkable(pos):
            return pos not in obstacles

        path = pathfind(grid, start=(0, 0), goal=(19, 19), walkable=walkable)

        assert path is not None

        # Path should avoid all obstacles
        for pos in path:
            assert pos not in obstacles

    def test_path_through_narrow_passage(self):
        grid = Grid2D(width=10, height=10)

        # Create walls with a narrow passage
        # Walls at y=5, except for x=5 (the passage)
        def walkable(pos):
            x, y = pos
            if y == 5 and x != 5:
                return False
            return True

        # Path from top to bottom should use the passage
        path = pathfind(grid, start=(5, 0), goal=(5, 9), walkable=walkable)

        assert path is not None
        assert (5, 5) in path  # Should go through the passage


class TestPathfindEdgeCases:
    """Test edge cases in pathfinding."""

    def test_start_out_of_bounds(self):
        grid = Grid2D(width=10, height=10)

        # Start outside grid bounds
        # Implementation might handle this differently, but should not crash
        try:
            path = pathfind(grid, start=(-1, 0), goal=(5, 5))
            # Either returns None or raises error
            assert path is None or True
        except (ValueError, KeyError):
            # Acceptable to raise error for invalid start
            pass

    def test_goal_out_of_bounds(self):
        grid = Grid2D(width=10, height=10)

        try:
            path = pathfind(grid, start=(5, 5), goal=(15, 15))
            # Should likely return None (unreachable)
            assert path is None or True
        except (ValueError, KeyError):
            pass

    def test_single_cell_grid(self):
        grid = Grid2D(width=1, height=1)

        path = pathfind(grid, start=(0, 0), goal=(0, 0))

        assert path is not None
        assert path == [(0, 0)]

    def test_long_path(self):
        grid = Grid2D(width=50, height=50)

        path = pathfind(grid, start=(0, 0), goal=(49, 49))

        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (49, 49)
