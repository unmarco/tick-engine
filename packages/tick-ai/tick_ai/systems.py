"""System factories for behavior trees and utility AI."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_ai.components import BehaviorTree, UtilityAgent
from tick_ai.evaluator import evaluate
from tick_ai.manager import AIManager

if TYPE_CHECKING:
    from tick import TickContext, World


def make_bt_system(
    manager: AIManager,
    on_status: Callable[["World", "TickContext", int, str], None] | None = None,
) -> Callable[["World", "TickContext"], None]:
    """Return a system that evaluates behavior trees each tick.

    on_status(world, ctx, eid, status_value) is called after each entity's
    tree evaluation completes (i.e. returns SUCCESS or FAILURE, not RUNNING).
    """

    def bt_system(world: World, ctx: TickContext) -> None:
        for eid, (bt,) in list(world.query(BehaviorTree)):
            tree_def = manager.tree(bt.tree_name)
            if tree_def is None:
                continue
            root_id, nodes = tree_def
            status, running, counts = evaluate(
                nodes, root_id, bt.running_node, bt.repeat_counts,
                manager, world, ctx, eid,
            )
            bt.running_node = running
            bt.status = status.value
            bt.repeat_counts = counts
            if on_status is not None and status.value in ("success", "failure"):
                on_status(world, ctx, eid, status.value)

    return bt_system


def make_utility_system(
    manager: AIManager,
    on_select: Callable[["World", "TickContext", int, str, float], None] | None = None,
) -> Callable[["World", "TickContext"], None]:
    """Return a system that evaluates utility selectors each tick.

    on_select(world, ctx, eid, action_name, score) is called after selection.
    """

    def utility_system(world: World, ctx: TickContext) -> None:
        for eid, (agent,) in list(world.query(UtilityAgent)):
            name, score = manager.select_action(
                agent.selector_name, world, eid,
            )
            agent.selected_action = name
            agent.score = score
            if on_select is not None and name:
                on_select(world, ctx, eid, name, score)

    return utility_system
