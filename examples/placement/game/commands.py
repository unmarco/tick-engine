"""Command dataclasses for the placement system."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceStructure:
    """Request to place a building at a grid coordinate."""
    name: str
    x: int
    y: int


@dataclass(frozen=True)
class Demolish:
    """Request to demolish whatever is at a grid coordinate."""
    x: int
    y: int
