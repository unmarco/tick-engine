"""Inventory component and helper functions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Inventory:
    """Mutable inventory component storing resource quantities.

    Attributes:
        slots: Mapping of resource_name -> quantity.
        capacity: Maximum total quantity across all resources (-1 for unlimited).
    """

    slots: dict[str, int] = field(default_factory=dict)
    capacity: int = -1


class InventoryHelper:
    """Pure functions for inventory manipulation."""

    @staticmethod
    def add(inv: Inventory, name: str, amount: int = 1) -> int:
        """Add resources, respecting capacity. Returns amount actually added."""
        if amount < 0:
            raise ValueError(f"amount must be >= 0, got {amount}")
        if amount == 0:
            return 0

        if inv.capacity == -1:
            inv.slots[name] = inv.slots.get(name, 0) + amount
            return amount

        total_used = sum(inv.slots.values())
        available = inv.capacity - total_used
        actual = min(amount, max(0, available))
        if actual > 0:
            inv.slots[name] = inv.slots.get(name, 0) + actual
        return actual

    @staticmethod
    def remove(inv: Inventory, name: str, amount: int = 1) -> int:
        """Remove resources. Returns amount actually removed."""
        if amount < 0:
            raise ValueError(f"amount must be >= 0, got {amount}")
        if amount == 0 or name not in inv.slots:
            return 0

        current = inv.slots[name]
        actual = min(amount, current)
        remaining = current - actual
        if remaining == 0:
            del inv.slots[name]
        else:
            inv.slots[name] = remaining
        return actual

    @staticmethod
    def count(inv: Inventory, name: str) -> int:
        """Get current quantity of a resource."""
        return inv.slots.get(name, 0)

    @staticmethod
    def total(inv: Inventory) -> int:
        """Get total quantity across all resource types."""
        return sum(inv.slots.values())

    @staticmethod
    def has(inv: Inventory, name: str, amount: int = 1) -> bool:
        """Check if at least *amount* of resource exists."""
        if amount < 0:
            raise ValueError(f"amount must be >= 0, got {amount}")
        return inv.slots.get(name, 0) >= amount

    @staticmethod
    def has_all(inv: Inventory, requirements: dict[str, int]) -> bool:
        """Check if all requirements are met."""
        for name, needed in requirements.items():
            if inv.slots.get(name, 0) < needed:
                return False
        return True

    @staticmethod
    def transfer(
        source: Inventory, target: Inventory, name: str, amount: int = 1
    ) -> int:
        """Move resources between inventories. Returns amount transferred."""
        if amount < 0:
            raise ValueError(f"amount must be >= 0, got {amount}")
        removed = InventoryHelper.remove(source, name, amount)
        added = InventoryHelper.add(target, name, removed)
        if added < removed:
            InventoryHelper.add(source, name, removed - added)
        return added

    @staticmethod
    def names(inv: Inventory) -> list[str]:
        """Get all resource type names currently in inventory."""
        return list(inv.slots.keys())

    @staticmethod
    def clear(inv: Inventory, name: str | None = None) -> None:
        """Remove all of one type, or everything if name is None."""
        if name is None:
            inv.slots.clear()
        else:
            inv.slots.pop(name, None)
