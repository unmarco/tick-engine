"""Integration tests — CellMap with tick-spatial pathfinding."""
from __future__ import annotations

from tick_atlas.cellmap import CellMap
from tick_atlas.types import CellDef
from tick_spatial.grid2d import Grid2D
from tick_spatial.grid3d import Grid3D
from tick_spatial.hexgrid import HexGrid
from tick_spatial.pathfind import pathfind

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=3.0)
WALL = CellDef(name="wall", passable=False)
ROAD = CellDef(name="road", move_cost=0.5)


class TestPathfindWalkable:
    def test_passable_as_walkable(self) -> None:
        grid = Grid2D(width=5, height=5)
        cells = CellMap(default=GRASS)
        path = pathfind(grid, (0, 0), (4, 0), walkable=cells.passable)
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (4, 0)

    def test_wall_blocks_path(self) -> None:
        grid = Grid2D(width=5, height=1)
        cells = CellMap(default=GRASS)
        cells.set((2, 0), WALL)
        path = pathfind(grid, (0, 0), (4, 0), walkable=cells.passable)
        assert path is None

    def test_wall_forces_detour(self) -> None:
        grid = Grid2D(width=5, height=3)
        cells = CellMap(default=GRASS)
        # Wall across middle row except edges
        cells.set((1, 1), WALL)
        cells.set((2, 1), WALL)
        cells.set((3, 1), WALL)
        path = pathfind(grid, (2, 0), (2, 2), walkable=cells.passable)
        assert path is not None
        # Path must go around the wall
        for coord in path:
            assert cells.passable(coord)


class TestPathfindCost:
    def test_move_cost_as_cost(self) -> None:
        grid = Grid2D(width=5, height=1)
        cells = CellMap(default=GRASS)
        path = pathfind(grid, (0, 0), (4, 0), cost=cells.move_cost)
        assert path is not None
        assert len(path) == 5

    def test_prefers_low_cost(self) -> None:
        grid = Grid2D(width=5, height=3)
        cells = CellMap(default=GRASS)
        # Make a road along y=0 and forest along y=1
        for x in range(5):
            cells.set((x, 0), ROAD)
        for x in range(5):
            cells.set((x, 1), FOREST)
        path = pathfind(grid, (0, 0), (4, 0), cost=cells.move_cost)
        assert path is not None
        # All steps should be on the road (y=0)
        for coord in path:
            assert coord[1] == 0


class TestPathfindCombined:
    def test_cost_and_walkable(self) -> None:
        grid = Grid2D(width=5, height=3)
        cells = CellMap(default=GRASS)
        cells.set((2, 0), WALL)
        cells.set((2, 2), WALL)
        # Must go through (2,1) which is grass
        path = pathfind(
            grid, (0, 0), (4, 0),
            cost=cells.move_cost, walkable=cells.passable,
        )
        assert path is not None
        for coord in path:
            assert cells.passable(coord)


class TestGridCompatibility:
    def test_grid3d(self) -> None:
        grid = Grid3D(width=3, height=3, depth=3)
        cells = CellMap(default=GRASS)
        cells.set((1, 1, 1), WALL)
        path = pathfind(grid, (0, 0, 0), (2, 2, 2), walkable=cells.passable)
        assert path is not None
        assert (1, 1, 1) not in path

    def test_hexgrid(self) -> None:
        grid = HexGrid(width=5, height=5)
        cells = CellMap(default=GRASS)
        path = pathfind(grid, (0, 0), (4, 4), cost=cells.move_cost)
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (4, 4)
