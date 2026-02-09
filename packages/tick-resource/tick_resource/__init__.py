"""tick-resource — Typed resource management for the tick engine."""
from tick_resource.inventory import Inventory, InventoryHelper
from tick_resource.recipe import Recipe, can_craft, craft
from tick_resource.registry import ResourceRegistry
from tick_resource.systems import make_resource_decay_system
from tick_resource.types import ResourceDef

__all__ = [
    "Inventory",
    "InventoryHelper",
    "Recipe",
    "ResourceDef",
    "ResourceRegistry",
    "can_craft",
    "craft",
    "make_resource_decay_system",
]
