"""tick-tween - Smooth value interpolation over time for the tick engine."""
from __future__ import annotations

from tick_tween.components import Tween
from tick_tween.easing import EASINGS
from tick_tween.systems import make_tween_system

__all__ = ["Tween", "EASINGS", "make_tween_system"]
