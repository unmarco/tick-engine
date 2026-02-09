"""Game components for the easing gallery."""
from dataclasses import dataclass


@dataclass
class OrbState:
    """Tracks an orb's animation state. progress is driven by Tween (0->1)."""

    progress: float = 0.0
    t: float = 0.0  # normalized time (elapsed/duration), for curve dot
    start_x: float = 0.0
    start_y: float = 0.0
    end_x: float = 0.0
    end_y: float = 0.0
    easing: str = "linear"
    lane: int = -1  # 0-3 for comparison, -1 for sandbox


@dataclass
class AutoWaveTag:
    """Singleton marker for the auto-wave timer entity."""

    pass
