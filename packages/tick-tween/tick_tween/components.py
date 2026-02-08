"""Tween component."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Tween:
    target: str
    field: str
    start_val: float
    end_val: float
    duration: int
    elapsed: int = 0
    easing: str = "linear"
