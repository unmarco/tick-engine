"""tick-colony - Reusable colony builder / roguelike simulation primitives."""
from __future__ import annotations

from typing import TYPE_CHECKING

# Components
from tick_colony.grid import Position
from tick_colony.actions import Action
from tick_colony.needs import NeedSet
from tick_colony.stats import StatBlock, Modifiers
from tick_colony.containment import Container, ContainedBy
from tick_colony.lifecycle import Lifecycle

# Framework objects
from tick_colony.grid import Grid
from tick_colony.events import EventLog, Event
from tick_colony.snapshot import ColonySnapshot

# System factories
from tick_colony.grid import make_grid_cleanup_system
from tick_colony.actions import make_action_system
from tick_colony.needs import make_need_decay_system
from tick_colony.stats import make_modifier_tick_system
from tick_colony.lifecycle import make_lifecycle_system

# Helpers
from tick_colony.needs import NeedHelper
from tick_colony.stats import effective, add_modifier, remove_modifiers
from tick_colony.containment import add_to_container, remove_from_container, transfer, contents, parent_of

if TYPE_CHECKING:
    from tick import World


def register_colony_components(world: World) -> None:
    for ctype in (Position, Action, NeedSet, StatBlock, Modifiers, Container, ContainedBy, Lifecycle):
        world.register_component(ctype)
