"""Cell type definitions for tick-atlas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CellDef:
    """Immutable cell type definition.

    Attributes:
        name: Unique identifier for this cell type.
        passable: Whether entities can traverse this cell.
        move_cost: Pathfinding edge weight (must be >= 0).
        properties: Arbitrary user data.
    """

    name: str
    passable: bool = True
    move_cost: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("CellDef name must be non-empty")
        if self.move_cost < 0:
            raise ValueError(f"move_cost must be >= 0, got {self.move_cost}")
