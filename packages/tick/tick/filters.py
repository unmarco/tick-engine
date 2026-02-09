"""Query filter sentinels for World.query()."""

from __future__ import annotations


class Not:
    """Exclude entities that have this component type."""

    __slots__ = ("ctype",)

    def __init__(self, ctype: type) -> None:
        self.ctype = ctype


class AnyOf:
    """Match entities that have at least one of these component types."""

    __slots__ = ("ctypes",)

    def __init__(self, *ctypes: type) -> None:
        if not ctypes:
            raise ValueError("AnyOf requires at least one component type")
        self.ctypes = ctypes
