"""World - entity and component storage with queries."""

from __future__ import annotations

import dataclasses
from typing import Any, Generator, TypeVar, cast

from tick.types import DeadEntityError, EntityId, SnapshotError

T = TypeVar("T")


class World:
    def __init__(self) -> None:
        self._components: dict[type, dict[int, Any]] = {}
        self._next_id: int = 0
        self._alive: set[int] = set()
        self._registry: dict[str, type] = {}

    def spawn(self) -> EntityId:
        eid = self._next_id
        self._next_id += 1
        self._alive.add(eid)
        return eid

    def despawn(self, entity_id: EntityId) -> None:
        self._alive.discard(entity_id)
        for store in self._components.values():
            store.pop(entity_id, None)

    def _register(self, ctype: type) -> None:
        key = f"{ctype.__module__}.{ctype.__qualname__}"
        self._registry[key] = ctype

    def register_component(self, ctype: type) -> None:
        """Explicit registration for cross-process restore."""
        self._register(ctype)

    def attach(self, entity_id: EntityId, component: Any) -> None:
        if entity_id not in self._alive:
            ctype = type(component)
            raise DeadEntityError(
                entity_id,
                f"Cannot attach {ctype.__name__} to dead entity {entity_id}",
            )
        ctype = type(component)
        self._register(ctype)
        if ctype not in self._components:
            self._components[ctype] = {}
        self._components[ctype][entity_id] = component

    def detach(self, entity_id: EntityId, component_type: type) -> None:
        store = self._components.get(component_type)
        if store is not None:
            store.pop(entity_id, None)

    def get(self, entity_id: EntityId, component_type: type[T]) -> T:
        if entity_id not in self._alive:
            raise DeadEntityError(
                entity_id, f"Entity {entity_id} is not alive"
            )
        store = self._components.get(component_type)
        if store is None or entity_id not in store:
            raise KeyError(
                f"Entity {entity_id} has no {component_type.__name__} component"
            )
        return cast(T, store[entity_id])

    def has(self, entity_id: EntityId, component_type: type) -> bool:
        if entity_id not in self._alive:
            return False
        store = self._components.get(component_type)
        return store is not None and entity_id in store

    def query(
        self, *component_types: type
    ) -> Generator[tuple[EntityId, tuple[Any, ...]], None, None]:
        if not component_types:
            return
        first = component_types[0]
        first_store = self._components.get(first)
        if first_store is None:
            return
        for eid in list(first_store):
            if eid not in self._alive:
                continue
            components = []
            for ctype in component_types:
                store = self._components.get(ctype)
                if store is None or eid not in store:
                    break
                components.append(store[eid])
            else:
                yield eid, tuple(components)

    def entities(self) -> frozenset[EntityId]:
        return frozenset(self._alive)

    def alive(self, entity_id: EntityId) -> bool:
        return entity_id in self._alive

    def snapshot(self) -> dict[str, Any]:
        components: dict[str, dict[str, dict[str, Any]]] = {}
        for ctype, store in self._components.items():
            if not store:
                continue
            key = f"{ctype.__module__}.{ctype.__qualname__}"
            if not dataclasses.is_dataclass(ctype):
                raise TypeError(
                    f"Cannot snapshot non-dataclass component {ctype.__qualname__}"
                )
            components[key] = {
                str(eid): dataclasses.asdict(comp)
                for eid, comp in store.items()
                if eid in self._alive
            }
        return {
            "entities": sorted(self._alive),
            "next_id": self._next_id,
            "components": components,
        }

    def restore(self, data: dict[str, Any]) -> None:
        self._alive = set(data["entities"])
        self._next_id = data["next_id"]
        self._components.clear()

        for type_name, store_data in data["components"].items():
            ctype = self._registry.get(type_name)
            if ctype is None:
                raise SnapshotError(
                    f"Unregistered component type: {type_name!r}"
                )
            store: dict[int, Any] = {}
            for eid_str, fields in store_data.items():
                store[int(eid_str)] = ctype(**fields)
            self._components[ctype] = store
