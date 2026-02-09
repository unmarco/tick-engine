"""Recipe dataclass and crafting functions."""
from __future__ import annotations

from dataclasses import dataclass, field

from tick_resource.inventory import Inventory, InventoryHelper


@dataclass(frozen=True)
class Recipe:
    """Immutable crafting recipe definition.

    Attributes:
        name: Recipe identifier.
        inputs: Resource requirements (resource_name -> quantity).
        outputs: Resources produced (resource_name -> quantity).
        duration: Ticks to complete (0 for instant). Metadata only.
    """

    name: str
    inputs: dict[str, int] = field(default_factory=dict)
    outputs: dict[str, int] = field(default_factory=dict)
    duration: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Recipe name must be non-empty")
        if self.duration < 0:
            raise ValueError(f"duration must be >= 0, got {self.duration}")


def can_craft(inventory: Inventory, recipe: Recipe) -> bool:
    """Check if inventory has all required inputs."""
    return InventoryHelper.has_all(inventory, recipe.inputs)


def craft(inventory: Inventory, recipe: Recipe) -> bool:
    """Consume inputs and produce outputs. Returns False if insufficient."""
    if not can_craft(inventory, recipe):
        return False
    for name, amount in recipe.inputs.items():
        InventoryHelper.remove(inventory, name, amount)
    for name, amount in recipe.outputs.items():
        InventoryHelper.add(inventory, name, amount)
    return True
