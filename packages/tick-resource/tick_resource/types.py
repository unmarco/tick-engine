"""Core data types for resource management."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResourceDef:
    """Immutable resource type definition.

    Attributes:
        name: Unique identifier for this resource type.
        max_stack: Maximum quantity per inventory slot (-1 for unlimited).
        properties: Arbitrary user metadata (e.g., {"edible": True}).
        decay_rate: Units lost per tick (0 for no decay).
    """

    name: str
    max_stack: int = -1
    properties: dict[str, Any] = field(default_factory=dict)
    decay_rate: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ResourceDef name must be non-empty")
        if self.max_stack < -1:
            raise ValueError(f"max_stack must be >= -1, got {self.max_stack}")
        if self.decay_rate < 0:
            raise ValueError(f"decay_rate must be >= 0, got {self.decay_rate}")
