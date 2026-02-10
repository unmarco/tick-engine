"""Game-specific components for the ecosystem arena."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Species:
    """Identifies an entity as predator or prey."""

    kind: str  # "predator" or "prey"


@dataclass
class Visual:
    """Rendering info: base color and radius (for drawing)."""

    color: tuple[int, int, int]
    radius: int
