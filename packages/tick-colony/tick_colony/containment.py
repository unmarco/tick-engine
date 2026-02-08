from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tick import EntityId, World


@dataclass
class Container:
    items: list[int] = field(default_factory=list)
    capacity: int = -1


@dataclass
class ContainedBy:
    parent: int = 0


def add_to_container(world: World, parent: int, child: int) -> bool:
    container = world.get(parent, Container)
    if container.capacity != -1 and len(container.items) >= container.capacity:
        return False
    container.items.append(child)
    world.attach(child, ContainedBy(parent=parent))
    return True


def remove_from_container(world: World, parent: int, child: int) -> None:
    container = world.get(parent, Container)
    if child in container.items:
        container.items.remove(child)
        world.detach(child, ContainedBy)


def transfer(world: World, child: int, old_parent: int, new_parent: int) -> bool:
    new_container = world.get(new_parent, Container)
    if new_container.capacity != -1 and len(new_container.items) >= new_container.capacity:
        return False
    remove_from_container(world, old_parent, child)
    new_container.items.append(child)
    world.attach(child, ContainedBy(parent=new_parent))
    return True


def contents(world: World, parent: int) -> list[int]:
    container = world.get(parent, Container)
    return list(container.items)


def parent_of(world: World, child: int) -> int | None:
    if not world.has(child, ContainedBy):
        return None
    return world.get(child, ContainedBy).parent
