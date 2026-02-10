"""Response curves for utility AI considerations.

All functions accept a float in [0.0, 1.0] and return a float in [0.0, 1.0].
Input is clamped to [0.0, 1.0] before evaluation.
"""
from __future__ import annotations

import math


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def linear(x: float, m: float = 1.0, b: float = 0.0) -> float:
    """Linear: y = m*x + b, clamped to [0, 1]."""
    return _clamp(m * _clamp(x) + b)


def quadratic(x: float, exp: float = 2.0) -> float:
    """Power curve: y = x^exp."""
    return _clamp(_clamp(x) ** exp)


def logistic(x: float, k: float = 10.0, midpoint: float = 0.5) -> float:
    """Logistic (sigmoid): steep transition around midpoint."""
    t = _clamp(x)
    return _clamp(1.0 / (1.0 + math.exp(-k * (t - midpoint))))


def inverse(x: float, steepness: float = 1.0) -> float:
    """Inverse: y = 1 - x^steepness."""
    return _clamp(1.0 - _clamp(x) ** steepness)


def step(x: float, threshold: float = 0.5) -> float:
    """Step: 0.0 below threshold, 1.0 at or above."""
    return 1.0 if _clamp(x) >= threshold else 0.0
