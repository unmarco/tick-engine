"""Layout, color, and rendering constants."""
from __future__ import annotations

# Grid defaults (overridden by CLI --map-size)
DEFAULT_MAP_SIZE = 20
DEFAULT_TILE_SIZE = 24

# Layout
SIDEBAR_W = 200
LOG_H = 80
FPS = 60

# Terrain colors
COLOR_GRASS = (70, 130, 60)
COLOR_FOREST = (30, 90, 30)
COLOR_WATER = (40, 80, 160)
COLOR_STOCKPILE = (180, 160, 80)

# Colonist state colors
STATE_COLORS: dict[str, tuple[int, int, int]] = {
    "idle": (180, 180, 180),
    "foraging": (100, 200, 80),
    "returning": (220, 180, 60),
    "resting": (100, 140, 220),
    "building": (200, 120, 60),
}

# Season tint overlays (r, g, b, alpha)
SEASON_TINTS: dict[str, tuple[int, int, int, int]] = {
    "spring": (60, 200, 80, 20),
    "summer": (240, 200, 50, 25),
    "autumn": (200, 100, 30, 20),
    "winter": (150, 180, 220, 30),
}

# UI colors
COLOR_BG = (20, 20, 30)
COLOR_SIDEBAR_BG = (25, 25, 35)
COLOR_LOG_BG = (18, 18, 25)
COLOR_TEXT = (200, 200, 200)
COLOR_TEXT_DIM = (130, 130, 140)
COLOR_SELECTED_RING = (255, 255, 255)
COLOR_NEED_BG = (40, 40, 50)
COLOR_HUNGER = (220, 80, 60)
COLOR_FATIGUE = (80, 140, 220)

# Event log colors
LOG_COLORS: dict[str, tuple[int, int, int]] = {
    "birth": (100, 220, 100),
    "death": (220, 60, 60),
    "season": (200, 200, 100),
    "event_start": (255, 160, 60),
    "event_end": (160, 160, 160),
    "ability": (180, 120, 255),
    "command": (100, 200, 220),
    "default": (170, 170, 170),
}


def compute_layout(map_size: int) -> dict[str, int]:
    """Compute layout dimensions from map size."""
    tile_size = max(12, min(24, 480 // map_size))
    grid_px = map_size * tile_size
    screen_w = grid_px + SIDEBAR_W
    screen_h = grid_px + LOG_H
    return {
        "tile_size": tile_size,
        "grid_px": grid_px,
        "screen_w": screen_w,
        "screen_h": screen_h,
        "map_size": map_size,
    }
