"""N-dimensional vector math helpers operating on tuple[float, ...]."""
from __future__ import annotations

import math

Vec = tuple[float, ...]


def add(a: Vec, b: Vec) -> Vec:
    return tuple(ai + bi for ai, bi in zip(a, b, strict=True))


def sub(a: Vec, b: Vec) -> Vec:
    return tuple(ai - bi for ai, bi in zip(a, b, strict=True))


def scale(v: Vec, s: float) -> Vec:
    return tuple(vi * s for vi in v)


def dot(a: Vec, b: Vec) -> float:
    return sum(ai * bi for ai, bi in zip(a, b, strict=True))


def magnitude_sq(v: Vec) -> float:
    return sum(vi * vi for vi in v)


def magnitude(v: Vec) -> float:
    return math.sqrt(magnitude_sq(v))


def normalize(v: Vec) -> Vec:
    mag = magnitude(v)
    if mag == 0.0:
        return v
    return scale(v, 1.0 / mag)


def distance_sq(a: Vec, b: Vec) -> float:
    return magnitude_sq(sub(a, b))


def distance(a: Vec, b: Vec) -> float:
    return math.sqrt(distance_sq(a, b))


def zero(dimensions: int) -> Vec:
    return tuple(0.0 for _ in range(dimensions))


def clamp_magnitude(v: Vec, max_mag: float) -> Vec:
    sq = magnitude_sq(v)
    if sq <= max_mag * max_mag:
        return v
    return scale(normalize(v), max_mag)
