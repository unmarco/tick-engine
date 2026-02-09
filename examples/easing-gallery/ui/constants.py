"""Layout constants and color definitions."""

# Timing
FPS = 60
TPS = 20

# Layout dimensions
LANE_COUNT = 4
LANE_H = 120
LABEL_W = 100
CURVE_W = 140
TRACK_W = 440
SIDEBAR_W = 140
STATUS_H = 36

SCREEN_W = LABEL_W + CURVE_W + TRACK_W + SIDEBAR_W
SCREEN_H = LANE_H * LANE_COUNT + STATUS_H

# Orb
ORB_RADIUS = 10
TRACK_PAD = 20  # padding inside the track

# Colors
BG_COLOR = (20, 20, 30)
LANE_BG = (30, 30, 45)
LANE_BORDER = (50, 50, 70)
CURVE_BG = (15, 15, 25)
TRACK_BG = (25, 25, 40)
TRACK_RAIL = (60, 60, 80)
SIDEBAR_BG = (25, 25, 38)
STATUS_BG = (35, 35, 50)
TEXT_COLOR = (200, 200, 210)
TEXT_DIM = (120, 120, 140)
LABEL_COLOR = (180, 180, 200)

# FSM state colors
STATE_WAITING = (128, 128, 128)
STATE_COMPLETED = (255, 255, 255)

# Easing name → color
EASING_COLORS: dict[str, tuple[int, int, int]] = {
    "linear": (0, 220, 220),
    "ease_in": (255, 160, 40),
    "ease_out": (60, 220, 80),
    "ease_in_out": (220, 80, 220),
}

EASING_NAMES = ["linear", "ease_in", "ease_out", "ease_in_out"]
