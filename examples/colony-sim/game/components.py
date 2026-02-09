"""Game-specific components."""
from __future__ import annotations

from dataclasses import dataclass

from tick_spatial import Coord


@dataclass
class Colonist:
    name: str


@dataclass
class Destination:
    coord: Coord


@dataclass
class VisualPos:
    """Smooth visual position driven by Tween."""
    prev_x: float = 0.0
    prev_y: float = 0.0
    curr_x: float = 0.0
    curr_y: float = 0.0
    progress: float = 1.0


@dataclass
class SelectedTag:
    """Marker component for the currently selected entity."""
    pass
