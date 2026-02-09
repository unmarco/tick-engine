"""BlueprintRegistry templates for colonist and stockpile entities."""
from __future__ import annotations

from tick_colony import BlueprintRegistry


def make_blueprints() -> BlueprintRegistry:
    """Define colonist and stockpile blueprints."""
    bp = BlueprintRegistry()

    bp.define("colonist", {
        "game.components.Colonist": {"name": "Unnamed"},
        "tick_spatial.components.Pos2D": {"x": 0.0, "y": 0.0},
        "tick_colony.needs.NeedSet": {"data": {}},
        "tick_colony.stats.StatBlock": {"data": {"strength": 8.0, "speed": 2.0}},
        "tick_colony.stats.Modifiers": {"entries": []},
        "tick_colony.lifecycle.Lifecycle": {"born_tick": 0, "max_age": 2000},
        "tick_fsm.components.FSM": {"state": "building", "transitions": {}},
        "game.components.VisualPos": {
            "prev_x": 0.0, "prev_y": 0.0,
            "curr_x": 0.0, "curr_y": 0.0,
            "progress": 1.0,
        },
    })

    bp.define("stockpile", {
        "tick_spatial.components.Pos2D": {"x": 0.0, "y": 0.0},
        "tick_resource.inventory.Inventory": {"capacity": 60},
    })

    return bp
