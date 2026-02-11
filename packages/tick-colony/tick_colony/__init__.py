"""tick-colony - Reusable colony builder / roguelike simulation primitives."""
from __future__ import annotations

from typing import TYPE_CHECKING

# Components (colony-unique)
from tick_colony.needs import NeedSet
from tick_colony.stats import StatBlock, Modifiers
from tick_colony.containment import Container, ContainedBy
from tick_colony.lifecycle import Lifecycle

# Framework objects (colony-unique)
from tick_colony.events import EventLog, Event
from tick_colony.snapshot import ColonySnapshot

# System factories (colony-unique)
from tick_colony.needs import make_need_decay_system
from tick_colony.stats import make_modifier_tick_system
from tick_colony.lifecycle import make_lifecycle_system

# Helpers (colony-unique)
from tick_colony.needs import NeedHelper
from tick_colony.stats import effective, add_modifier, remove_modifiers
from tick_colony.containment import add_to_container, remove_from_container, transfer, contents, parent_of

# Re-export adopted extensions for colony users
from tick_spatial import Grid2D, Pos2D, pathfind, make_spatial_cleanup_system
from tick_schedule import Timer, make_timer_system
from tick_fsm import FSM, FSMGuards, make_fsm_system
from tick_blueprint import BlueprintRegistry
from tick_signal import SignalBus
from tick_event import EventScheduler, EventGuards, EventDef, CycleDef, make_event_system

# Re-export tick-command
from tick_command import CommandQueue, make_command_system, expand_footprint, resolve_footprint

# Re-export tick-atlas
from tick_atlas import CellDef, CellMap

# Re-export tick-ability
from tick_ability import AbilityDef, AbilityState, AbilityGuards, AbilityManager, make_ability_system

# Re-export tick-resource
from tick_resource import (
    Inventory, InventoryHelper, Recipe, ResourceDef, ResourceRegistry,
    can_craft, craft, make_resource_decay_system,
)

# Re-export tick-ai
from tick_ai import (
    AIManager, BehaviorTree, Blackboard, UtilityAgent,
    Status, Node, make_bt_system, make_utility_system,
)

# Re-export tick-llm
from tick_llm import (
    LLMAgent, LLMClient, LLMConfig, LLMManager, LLMSystem,
    MockClient, ContextFn, ParserFn,
    default_json_parser, strip_code_fences, make_llm_system,
)

# Colony-specific LLM integration
from tick_colony.context import (
    make_resource_context, make_population_context,
    make_spatial_context, make_event_context, make_colony_context,
)
from tick_colony.directive import DirectiveHandler, make_directive_parser
from tick_colony.pressure import PressureThresholds, make_pressure_system

if TYPE_CHECKING:
    from tick import World


def register_colony_components(world: World) -> None:
    for ctype in (Pos2D, Timer, FSM, NeedSet, StatBlock, Modifiers,
                  Container, ContainedBy, Lifecycle, Inventory,
                  LLMAgent, Blackboard):
        world.register_component(ctype)
