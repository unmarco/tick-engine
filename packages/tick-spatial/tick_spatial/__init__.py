"""tick-spatial - Spatial indexing for the tick engine."""
from __future__ import annotations

from tick_spatial.types import Pos2D, SpatialIndex
from tick_spatial.grid2d import Grid2D
from tick_spatial.hexgrid import HexGrid
from tick_spatial.pathfind import pathfind
from tick_spatial.systems import make_spatial_cleanup_system

__all__ = [
    "Pos2D",
    "SpatialIndex",
    "Grid2D",
    "HexGrid",
    "pathfind",
    "make_spatial_cleanup_system",
]
