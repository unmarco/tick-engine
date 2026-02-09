"""Building definitions and blueprint registry setup."""
from tick_blueprint import BlueprintRegistry

from game.components import Structure


def make_blueprints() -> BlueprintRegistry:
    """Create and return the building blueprint registry."""
    bp = BlueprintRegistry()

    # Keys must match module.qualname for world._registry lookup
    structure_key = f"{Structure.__module__}.{Structure.__qualname__}"
    pos_key = "tick_spatial.types.Pos2D"

    bp.define("farm", {
        structure_key: {"name": "farm"},
        pos_key: {"x": 0, "y": 0},
    }, meta={
        "footprint": (2, 2),
        "terrain_reqs": {"terrain": "grass"},
        "label": "Farm",
        "key": "1",
    })

    bp.define("mine", {
        structure_key: {"name": "mine"},
        pos_key: {"x": 0, "y": 0},
    }, meta={
        "footprint": (2, 2),
        "terrain_reqs": {"rocky": True},
        "label": "Mine",
        "key": "2",
    })

    bp.define("barracks", {
        structure_key: {"name": "barracks"},
        pos_key: {"x": 0, "y": 0},
    }, meta={
        "footprint": (3, 2),
        "terrain_reqs": {"terrain": "grass"},
        "label": "Barracks",
        "key": "3",
    })

    bp.define("tower", {
        structure_key: {"name": "tower"},
        pos_key: {"x": 0, "y": 0},
    }, meta={
        "footprint": (1, 1),
        "terrain_reqs": {},
        "label": "Tower",
        "key": "4",
    })

    bp.define("road", {
        structure_key: {"name": "road"},
        pos_key: {"x": 0, "y": 0},
    }, meta={
        "footprint": (1, 1),
        "terrain_reqs": {},
        "label": "Road",
        "key": "5",
        "stackable": True,
    })

    return bp


BUILDING_NAMES = ["farm", "mine", "barracks", "tower", "road"]

BUILDING_COLORS: dict[str, tuple[int, int, int]] = {
    "farm": (200, 170, 50),
    "mine": (100, 80, 60),
    "barracks": (180, 50, 50),
    "tower": (100, 100, 180),
    "road": (160, 160, 160),
}
