"""ECS components for AI entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BehaviorTree:
    """Assigns a behavior tree definition to an entity."""

    tree_name: str
    running_node: str = ""
    status: str = ""
    repeat_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class Blackboard:
    """Per-entity key-value knowledge store."""

    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class UtilityAgent:
    """Assigns a utility selector to an entity."""

    selector_name: str
    selected_action: str = ""
    score: float = 0.0
