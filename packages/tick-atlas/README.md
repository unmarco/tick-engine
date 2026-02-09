# tick-atlas

Cell/tile property maps for the tick engine. Associates terrain types, movement costs, passability, and arbitrary properties with grid coordinates. A companion to tick-spatial -- it gives the space itself properties.

## Install

```bash
pip install tick-atlas
```

```python
from tick_atlas import CellDef, CellMap
```

## Quick Example

```python
from tick_spatial import Grid2D, pathfind
from tick_atlas import CellDef, CellMap

# Define terrain types
grass = CellDef(name="grass")
forest = CellDef(name="forest", move_cost=3.0, properties={"trees": True})
wall = CellDef(name="wall", passable=False)

# Create a cell map with grass as default
cells = CellMap(default=grass)
cells.set((5, 5), forest)
cells.fill_rect((2, 3), (4, 3), wall)

# Works directly with pathfind -- no wrappers needed
grid = Grid2D(width=20, height=20)
path = pathfind(grid, (0, 0), (10, 10), cost=cells.move_cost, walkable=cells.passable)
```

## API Reference

### CellDef

```python
CellDef(
    name: str,                    # unique identifier
    passable: bool = True,        # can entities traverse?
    move_cost: float = 1.0,       # pathfinding edge weight (>= 0)
    properties: dict[str, Any] = {},  # arbitrary user data
)
```

Frozen dataclass. Validates that `name` is non-empty and `move_cost >= 0`.

### CellMap

```python
CellMap(default: CellDef)
```

Sparse, dimension-agnostic cell property storage. Only non-default cells are stored.

#### Mutation

| Method | Signature | Notes |
|--------|-----------|-------|
| `set` | `(coord, cell_def)` | Auto-registers. Setting to default removes from storage. |
| `clear` | `(coord)` | Reset to default. |
| `clear_all` | `()` | Reset everything. |
| `fill` | `(coords, cell_def)` | Set list of coords. |
| `fill_rect` | `(corner1, corner2, cell_def)` | 2D rectangle fill (inclusive). |
| `register` | `(cell_def)` | Explicit registration for restore. |

#### Queries

| Method | Signature | Notes |
|--------|-----------|-------|
| `at` | `(coord) -> CellDef` | Returns default for unset coords. |
| `passable` | `(coord) -> bool` | Matches `pathfind(walkable=...)`. |
| `move_cost` | `(from, to) -> float` | Uses destination cost. Matches `pathfind(cost=...)`. |
| `matches` | `(coord, requirements) -> bool` | Check cell against a requirements dict (see below). |
| `of_type` | `(name) -> list[Coord]` | All coords with given cell type (non-default only). |
| `coords` | `() -> list[Coord]` | All non-default coordinates. |
| `default` | property | The default cell type. |

#### Snapshot / Restore

```python
snap = cells.snapshot()
# {"default": "grass", "cells": {"3,5": "forest", "10,10": "water"}}

cells2 = CellMap(default=grass)
cells2.register(forest)
cells2.restore(snap)
```

All CellDefs must be registered before `restore()`. Coordinates are serialized as comma-separated strings, supporting any dimensionality.

### Cell Matching

`matches()` checks if a cell satisfies a dict of requirements. The special key `"terrain"` compares against the CellDef name; all other keys compare against CellDef properties. Returns `False` for default (sparse) cells.

```python
farmland = CellDef(name="farmland", properties={"buildable": True, "fertile": True})
cells.set((5, 3), farmland)

cells.matches((5, 3), {"buildable": True})                     # True
cells.matches((5, 3), {"terrain": "farmland", "fertile": True}) # True
cells.matches((5, 3), {"buildable": False})                     # False
cells.matches((0, 0), {"buildable": True})                      # False (default cell)
```

### Pathfind Integration

`CellMap.passable` and `CellMap.move_cost` match the `pathfind()` callback signatures directly:

```python
path = pathfind(grid, start, goal, cost=cells.move_cost, walkable=cells.passable)
```

Works with Grid2D, Grid3D, and HexGrid.

## Part of [tick-engine](../../README.md)

MIT License
