# tick-spatial

Spatial indexing and A* pathfinding for the tick engine. Provides a 2D grid (Chebyshev, 8-directional) and a hex grid (axial coordinates, 6-directional), both implementing the same `SpatialIndex` protocol.

## Install

```bash
pip install tick-spatial
```

```python
from tick_spatial import Pos2D, Grid2D, HexGrid, pathfind, make_spatial_cleanup_system
```

## Quick Example

```python
from tick import Engine
from tick_spatial import Pos2D, Grid2D, pathfind, make_spatial_cleanup_system

engine = Engine(tps=10)
grid = Grid2D(width=20, height=20)

# Place entities on the grid
e = engine.world.spawn()
engine.world.attach(e, Pos2D(x=0, y=0))
grid.place(e, 0, 0)

# A* pathfinding
path = pathfind(grid, start=(0, 0), goal=(5, 3))
print(path)  # [(0, 0), (1, 1), (2, 2), (3, 3), (4, 3), (5, 3)]

# Radius query
nearby = grid.in_radius(0, 0, r=2)  # [(eid, x, y), ...]

# Auto-remove despawned entities from the index
engine.add_system(make_spatial_cleanup_system(grid))
```

## Grid Types

### Grid2D

```python
Grid2D(width: int, height: int)
```

Standard 2D integer grid. Uses Chebyshev distance (diagonal movement costs the same as cardinal). 8-directional neighbors.

### HexGrid

```python
HexGrid(width: int, height: int)
```

Hexagonal grid using axial coordinates (q, r). 6-directional neighbors. Flat-top orientation.

Both implement the `SpatialIndex` protocol and work interchangeably with `pathfind()`.

## API Reference

### Pos2D

```python
Pos2D(x: float, y: float)
```

Dataclass component for 2D position. Used by `rebuild()` to sync the grid from world state.

### SpatialIndex Protocol

All grid types implement these methods:

| Method | Description |
|--------|-------------|
| `.place(eid, x, y)` | Add entity at position (removes from old position first) |
| `.move(eid, x, y)` | Move entity to new position (raises `KeyError` if not placed) |
| `.remove(eid)` | Remove entity from index |
| `.at(x, y) -> frozenset[int]` | Entity IDs at a position |
| `.position_of(eid) -> (x, y) or None` | Where is this entity? |
| `.in_radius(x, y, r) -> list[(eid, x, y)]` | All entities within radius |
| `.neighbors(x, y) -> list[(x, y)]` | Adjacent cells |
| `.heuristic(a, b) -> float` | Distance estimate for A* |
| `.tracked_entities() -> frozenset[int]` | All entity IDs in the index |
| `.rebuild(world)` | Rebuild index from `Pos2D` components in the world |

### pathfind

```python
pathfind(
    index: SpatialIndex,
    start: tuple[int, int],
    goal: tuple[int, int],
    cost: ((from, to) -> float) | None = None,
    walkable: ((x, y) -> bool) | None = None,
) -> list[tuple[int, int]] | None
```

A* search over any `SpatialIndex`. Returns a list of coordinates from start to goal (inclusive), or `None` if no path exists. Default step cost is `1.0`. The `walkable` predicate filters impassable cells.

### make_spatial_cleanup_system

```python
make_spatial_cleanup_system(index: SpatialIndex) -> System
```

Returns a system that removes despawned entities from the spatial index each tick.

## Part of [tick-engine](../../README.md)

MIT License
