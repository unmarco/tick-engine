"""System factory for resource decay."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_resource.inventory import Inventory, InventoryHelper
from tick_resource.registry import ResourceRegistry

if TYPE_CHECKING:
    from tick import TickContext, World


def make_resource_decay_system(
    registry: ResourceRegistry,
    on_spoiled: Callable[..., None] | None = None,
) -> Callable[..., None]:
    """Return a system that processes resource decay each tick.

    ``on_spoiled(world, ctx, entity_id, resource_name, amount_lost)``
    fires when resources are lost to decay.
    """

    def resource_decay_system(world: World, ctx: TickContext) -> None:
        for eid, (inv,) in list(world.query(Inventory)):
            resource_names = list(inv.slots.keys())
            for name in resource_names:
                if not registry.has(name):
                    continue
                defn = registry.get(name)
                if defn.decay_rate == 0:
                    continue
                current = inv.slots.get(name, 0)
                if current == 0:
                    continue
                loss = min(defn.decay_rate, current)
                removed = InventoryHelper.remove(inv, name, loss)
                if on_spoiled is not None and removed > 0:
                    on_spoiled(world, ctx, eid, name, removed)

    return resource_decay_system
