"""BT traversal engine — pure functions, no side effects on the manager."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tick_ai.nodes import (
    Action,
    AlwaysFail,
    Condition,
    Inverter,
    Node,
    Parallel,
    Repeater,
    Selector,
    Sequence,
    Status,
    Succeeder,
    UtilitySelector,
)

if TYPE_CHECKING:
    from tick import TickContext, World

    from tick_ai.manager import AIManager


def evaluate(
    nodes: dict[str, Node],
    root_id: str,
    running_node: str,
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str, dict[str, int]]:
    """Evaluate a behavior tree for one tick.

    Returns (status, new_running_node, new_repeat_counts).
    """
    new_counts = dict(repeat_counts)
    ancestry = _build_ancestry(nodes, root_id)
    running_ancestors = _ancestor_set(running_node, ancestry) if running_node else set()

    status, new_running = _eval_node(
        root_id, nodes, running_node, running_ancestors,
        new_counts, manager, world, ctx, eid,
    )
    if status != Status.RUNNING:
        new_running = ""
    return status, new_running, new_counts


def _build_ancestry(
    nodes: dict[str, Node], root_id: str,
) -> dict[str, str]:
    """Build child->parent map by traversing from root."""
    parent_of: dict[str, str] = {}
    stack = [root_id]
    while stack:
        nid = stack.pop()
        node = nodes.get(nid)
        if node is None:
            continue
        for child_id in _children_of(node):
            parent_of[child_id] = nid
            stack.append(child_id)
    return parent_of


def _ancestor_set(node_id: str, ancestry: dict[str, str]) -> set[str]:
    """All ancestors of node_id (inclusive)."""
    result: set[str] = set()
    current: str | None = node_id
    while current is not None:
        result.add(current)
        current = ancestry.get(current)
    return result


def _children_of(node: Node) -> tuple[str, ...]:
    """Extract child IDs from a node."""
    if isinstance(node, (Action, Condition)):
        return ()
    if isinstance(node, (Sequence, Selector, Parallel, UtilitySelector)):
        return node.children
    if isinstance(node, (Inverter, Repeater, Succeeder, AlwaysFail)):
        return (node.child,) if node.child else ()
    return ()


def _eval_node(
    node_id: str,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    """Evaluate a single node, dispatching by type. Returns (status, running_id)."""
    node = nodes[node_id]

    if isinstance(node, Action):
        return _eval_action(node, manager, world, ctx, eid)
    if isinstance(node, Condition):
        return _eval_condition(node, manager, world, eid)
    if isinstance(node, Sequence):
        return _eval_sequence(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, Selector):
        return _eval_selector(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, Parallel):
        return _eval_parallel(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, UtilitySelector):
        return _eval_utility_selector(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, Inverter):
        return _eval_inverter(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, Repeater):
        return _eval_repeater(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, Succeeder):
        return _eval_succeeder(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    if isinstance(node, AlwaysFail):
        return _eval_always_fail(
            node, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
    return (Status.FAILURE, "")


# --- Leaf evaluators ---


def _eval_action(
    node: Action, manager: AIManager, world: World, ctx: TickContext, eid: int,
) -> tuple[Status, str]:
    fn = manager.action(node.action)
    if fn is None:
        return (Status.FAILURE, "")
    status = fn(world, ctx, eid)
    if status == Status.RUNNING:
        return (Status.RUNNING, node.id)
    return (status, "")


def _eval_condition(
    node: Condition, manager: AIManager, world: World, eid: int,
) -> tuple[Status, str]:
    fn = manager.condition(node.condition)
    if fn is None:
        return (Status.FAILURE, "")
    return (Status.SUCCESS if fn(world, eid) else Status.FAILURE, "")


# --- Composite evaluators ---


def _eval_sequence(
    node: Sequence,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    resume = running_node and node.id in running_ancestors
    for child_id in node.children:
        if resume and child_id not in running_ancestors:
            continue
        resume = False
        status, running_id = _eval_node(
            child_id, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
        if status != Status.SUCCESS:
            return (status, running_id)
    return (Status.SUCCESS, "")


def _eval_selector(
    node: Selector,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    resume = running_node and node.id in running_ancestors
    for child_id in node.children:
        if resume and child_id not in running_ancestors:
            continue
        resume = False
        status, running_id = _eval_node(
            child_id, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
        if status != Status.FAILURE:
            return (status, running_id)
    return (Status.FAILURE, "")


def _eval_parallel(
    node: Parallel,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    successes = 0
    failures = 0
    last_running_id = ""
    for child_id in node.children:
        status, running_id = _eval_node(
            child_id, nodes, running_node, running_ancestors,
            repeat_counts, manager, world, ctx, eid,
        )
        if status == Status.SUCCESS:
            successes += 1
        elif status == Status.FAILURE:
            failures += 1
        else:
            last_running_id = running_id

    total = len(node.children)
    if node.policy == "require_all":
        if failures > 0:
            return (Status.FAILURE, "")
        if successes == total:
            return (Status.SUCCESS, "")
        return (Status.RUNNING, last_running_id)
    else:  # require_one
        if successes > 0:
            return (Status.SUCCESS, "")
        if failures == total:
            return (Status.FAILURE, "")
        return (Status.RUNNING, last_running_id)


def _eval_utility_selector(
    node: UtilitySelector,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    if not node.children:
        return (Status.FAILURE, "")

    # If we have a running child, continue it
    if running_node and node.id in running_ancestors:
        for child_id in node.children:
            if child_id in running_ancestors:
                return _eval_node(
                    child_id, nodes, running_node, running_ancestors,
                    repeat_counts, manager, world, ctx, eid,
                )

    # Score each child by looking at the subtree root node's action name
    best_id = ""
    best_score = -1.0
    for child_id in node.children:
        child_node = nodes[child_id]
        # Score based on the child's action name in utility_actions
        score = _score_subtree(child_node, manager, world, eid)
        if score > best_score:
            best_score = score
            best_id = child_id

    if not best_id:
        return (Status.FAILURE, "")

    return _eval_node(
        best_id, nodes, running_node, running_ancestors,
        repeat_counts, manager, world, ctx, eid,
    )


def _score_subtree(
    node: Node, manager: AIManager, world: World, eid: int,
) -> float:
    """Score a node for UtilitySelector. Uses the node's action name if it's
    an Action node, otherwise returns 0.0."""
    if isinstance(node, Action):
        return manager.score_action(node.action, world, eid)
    return 0.0


# --- Decorator evaluators ---


def _eval_inverter(
    node: Inverter,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    status, running_id = _eval_node(
        node.child, nodes, running_node, running_ancestors,
        repeat_counts, manager, world, ctx, eid,
    )
    if status == Status.SUCCESS:
        return (Status.FAILURE, "")
    if status == Status.FAILURE:
        return (Status.SUCCESS, "")
    return (Status.RUNNING, running_id)


def _eval_repeater(
    node: Repeater,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    count = repeat_counts.get(node.id, 0)

    status, running_id = _eval_node(
        node.child, nodes, running_node, running_ancestors,
        repeat_counts, manager, world, ctx, eid,
    )

    if status == Status.RUNNING:
        return (Status.RUNNING, running_id)

    if status == Status.FAILURE and node.fail_policy == "fail":
        repeat_counts.pop(node.id, None)
        return (Status.FAILURE, "")

    count += 1
    if count >= node.max_count:
        repeat_counts.pop(node.id, None)
        return (Status.SUCCESS, "")

    repeat_counts[node.id] = count
    return (Status.RUNNING, node.id)


def _eval_succeeder(
    node: Succeeder,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    status, running_id = _eval_node(
        node.child, nodes, running_node, running_ancestors,
        repeat_counts, manager, world, ctx, eid,
    )
    if status == Status.RUNNING:
        return (Status.RUNNING, running_id)
    return (Status.SUCCESS, "")


def _eval_always_fail(
    node: AlwaysFail,
    nodes: dict[str, Node],
    running_node: str,
    running_ancestors: set[str],
    repeat_counts: dict[str, int],
    manager: AIManager,
    world: World,
    ctx: TickContext,
    eid: int,
) -> tuple[Status, str]:
    status, running_id = _eval_node(
        node.child, nodes, running_node, running_ancestors,
        repeat_counts, manager, world, ctx, eid,
    )
    if status == Status.RUNNING:
        return (Status.RUNNING, running_id)
    return (Status.FAILURE, "")
