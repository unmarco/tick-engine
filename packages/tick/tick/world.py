"""World - entity and component storage with queries."""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Generator, TypeVar, Union, cast

from tick.filters import AnyOf, Not
from tick.types import DeadEntityError, EntityId, SnapshotError

T = TypeVar("T")

# Query arguments: plain component types or filter sentinels.
QueryArg = Union[type, Not, AnyOf]

# Hook callback signature.
HookCallback = Callable[["World", EntityId, Any], None]


class World:
    def __init__(self) -> None:
        self._components: dict[type, dict[int, Any]] = {}
        self._next_id: int = 0
        self._alive: set[int] = set()
        self._registry: dict[str, type] = {}
        self._on_attach: dict[type, list[HookCallback]] = {}
        self._on_detach: dict[type, list[HookCallback]] = {}
        self._hooks_enabled: bool = True

    def spawn(self) -> EntityId:
        eid = self._next_id
        self._next_id += 1
        self._alive.add(eid)
        return eid

    def despawn(self, entity_id: EntityId) -> None:
        self._alive.discard(entity_id)
        for ctype, store in self._components.items():
            component = store.pop(entity_id, None)
            if component is not None and self._hooks_enabled:
                for cb in self._on_detach.get(ctype, ()):
                    cb(self, entity_id, component)

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
        if self._hooks_enabled:
            for cb in self._on_attach.get(ctype, ()):
                cb(self, entity_id, component)

    def detach(self, entity_id: EntityId, component_type: type) -> None:
        store = self._components.get(component_type)
        if store is not None:
            component = store.pop(entity_id, None)
            if component is not None and self._hooks_enabled:
                for cb in self._on_detach.get(component_type, ()):
                    cb(self, entity_id, component)

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
        self, *args: QueryArg
    ) -> Generator[tuple[EntityId, tuple[Any, ...]], None, None]:
        if not args:
            return

        required: list[type] = []
        excluded: list[type] = []
        any_groups: list[tuple[type, ...]] = []

        for arg in args:
            if isinstance(arg, Not):
                excluded.append(arg.ctype)
            elif isinstance(arg, AnyOf):
                any_groups.append(arg.ctypes)
            else:
                required.append(arg)

        # Choose iteration base.
        if required:
            base_store = self._components.get(required[0])
            if base_store is None:
                return
            candidates = list(base_store)
        elif any_groups:
            # Union of entity ids from the first AnyOf group.
            eids: set[int] = set()
            for ct in any_groups[0]:
                store = self._components.get(ct)
                if store is not None:
                    eids.update(store)
            candidates = list(eids)
        else:
            # Only Not filters — iterate all alive entities.
            candidates = list(self._alive)

        for eid in candidates:
            if eid not in self._alive:
                continue

            # Check Not filters.
            skip = False
            for ctype in excluded:
                ex_store = self._components.get(ctype)
                if ex_store is not None and eid in ex_store:
                    skip = True
                    break
            if skip:
                continue

            # Check AnyOf filters.
            for group in any_groups:
                found = False
                for ctype in group:
                    a_store = self._components.get(ctype)
                    if a_store is not None and eid in a_store:
                        found = True
                        break
                if not found:
                    skip = True
                    break
            if skip:
                continue

            # Collect required components.
            components: list[Any] = []
            for ctype in required:
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

    # -- Change detection hooks --

    def on_attach(
        self, ctype: type, callback: HookCallback
    ) -> None:
        self._on_attach.setdefault(ctype, []).append(callback)

    def on_detach(
        self, ctype: type, callback: HookCallback
    ) -> None:
        self._on_detach.setdefault(ctype, []).append(callback)

    def off_attach(
        self, ctype: type, callback: HookCallback
    ) -> None:
        cbs = self._on_attach.get(ctype)
        if cbs:
            try:
                cbs.remove(callback)
            except ValueError:
                pass

    def off_detach(
        self, ctype: type, callback: HookCallback
    ) -> None:
        cbs = self._on_detach.get(ctype)
        if cbs:
            try:
                cbs.remove(callback)
            except ValueError:
                pass

    # -- Snapshot / restore --

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
        self._hooks_enabled = False
        try:
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
        finally:
            self._hooks_enabled = True
