"""tick-spatial - Spatial indexing for the tick engine."""
from __future__ import annotations

from tick_spatial.types import Coord, Pos2D, Pos3D, SpatialIndex
from tick_spatial.grid2d import Grid2D
from tick_spatial.grid3d import Grid3D
from tick_spatial.hexgrid import HexGrid
from tick_spatial.pathfind import pathfind
from tick_spatial.systems import make_spatial_cleanup_system

__all__ = [
    "Coord",
    "Pos2D",
    "Pos3D",
    "SpatialIndex",
    "Grid2D",
    "Grid3D",
    "HexGrid",
    "pathfind",
    "make_spatial_cleanup_system",
]
