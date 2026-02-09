"""Footprint utilities — coord math for multi-tile placement."""
from __future__ import annotations

from tick_command.types import Coord


def expand_footprint(origin: Coord, dimensions: tuple[int, ...]) -> list[Coord]:
    """Expand a rectangular footprint from *origin* with *dimensions*.

    Both *origin* and *dimensions* must have the same number of elements.
    Returns all integer coordinates in the rectangle
    ``[origin, origin + dimensions)`` (exclusive upper bound).

    >>> expand_footprint((5, 3), (2, 2))
    [(5, 3), (5, 4), (6, 3), (6, 4)]
    """
    if len(origin) != len(dimensions):
        raise ValueError(
            f"origin has {len(origin)} dimensions but dimensions "
            f"has {len(dimensions)}"
        )
    for d in dimensions:
        if d < 1:
            raise ValueError(f"All dimensions must be >= 1, got {d}")
    return _expand(origin, dimensions, 0)


def _expand(
    origin: Coord,
    dimensions: tuple[int, ...],
    axis: int,
) -> list[Coord]:
    """Recursive helper for N-dimensional expansion."""
    if axis == len(dimensions):
        return [origin]
    results: list[Coord] = []
    for i in range(dimensions[axis]):
        shifted = origin[:axis] + (origin[axis] + i,) + origin[axis + 1 :]
        results.extend(_expand(shifted, dimensions, axis + 1))
    return results


def resolve_footprint(
    origin: Coord,
    shape: tuple[int, ...] | list[Coord],
) -> list[Coord]:
    """Normalise either form to absolute coordinates.

    *shape* can be:
    - A dimensions tuple ``(w, h, ...)`` → rectangular expansion.
    - A list of relative offsets ``[(0,0), (1,0), ...]`` → translated.
    """
    if isinstance(shape, tuple):
        return expand_footprint(origin, shape)
    # List of relative offsets
    result: list[Coord] = []
    for offset in shape:
        if len(offset) != len(origin):
            raise ValueError(
                f"Offset {offset} has {len(offset)} dimensions but "
                f"origin has {len(origin)}"
            )
        result.append(tuple(o + d for o, d in zip(origin, offset)))
    return result
