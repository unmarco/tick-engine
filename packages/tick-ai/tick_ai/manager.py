"""AIManager — central registry for trees, actions, conditions, and utility."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

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


ActionFn = Callable[["World", "TickContext", int], Status]
ConditionFn = Callable[["World", int], bool]
ConsiderationFn = Callable[["World", int], float]


class AIManager:
    """Manages behavior tree definitions, action/condition/consideration
    registrations, and utility AI selectors.
    """

    def __init__(self) -> None:
        # BT tree definitions: name -> (root_id, nodes dict)
        self._trees: dict[str, tuple[str, dict[str, Node]]] = {}
        # Action callbacks
        self._actions: dict[str, ActionFn] = {}
        # Condition callbacks
        self._conditions: dict[str, ConditionFn] = {}
        # Consideration callbacks (return 0.0-1.0)
        self._considerations: dict[str, ConsiderationFn] = {}
        # Utility actions: action_name -> list of consideration names
        self._utility_actions: dict[str, list[str]] = {}
        # Utility selectors: selector_name -> list of action names
        self._utility_selectors: dict[str, list[str]] = {}

    # --- Tree definitions ---

    def define_tree(
        self, name: str, root_id: str, nodes: dict[str, Node]
    ) -> None:
        """Register a behavior tree definition. Validates the node graph."""
        self._validate_tree(root_id, nodes)
        self._trees[name] = (root_id, nodes)

    def tree(self, name: str) -> tuple[str, dict[str, Node]] | None:
        """Look up a tree definition by name."""
        return self._trees.get(name)

    # --- Action registration ---

    def register_action(self, name: str, fn: ActionFn) -> None:
        """Register an action callback: (World, TickContext, eid) -> Status."""
        self._actions[name] = fn

    def action(self, name: str) -> ActionFn | None:
        """Look up a registered action."""
        return self._actions.get(name)

    # --- Condition registration ---

    def register_condition(self, name: str, fn: ConditionFn) -> None:
        """Register a condition callback: (World, eid) -> bool."""
        self._conditions[name] = fn

    def condition(self, name: str) -> ConditionFn | None:
        """Look up a registered condition."""
        return self._conditions.get(name)

    # --- Consideration registration ---

    def register_consideration(self, name: str, fn: ConsiderationFn) -> None:
        """Register a consideration callback: (World, eid) -> float [0.0-1.0]."""
        self._considerations[name] = fn

    def consideration(self, name: str) -> ConsiderationFn | None:
        """Look up a registered consideration."""
        return self._considerations.get(name)

    # --- Utility AI ---

    def define_utility_action(
        self, action_name: str, considerations: list[str]
    ) -> None:
        """Define a utility action with its consideration list."""
        self._utility_actions[action_name] = list(considerations)

    def define_utility_selector(
        self, name: str, action_names: list[str]
    ) -> None:
        """Define a utility selector that picks among utility actions."""
        self._utility_selectors[name] = list(action_names)

    def score_action(self, action_name: str, world: World, eid: int) -> float:
        """Score a utility action for an entity. Multiplicative combination."""
        considerations = self._utility_actions.get(action_name)
        if considerations is None:
            return 0.0
        if not considerations:
            return 0.0
        score = 1.0
        for name in considerations:
            fn = self._considerations.get(name)
            if fn is None:
                return 0.0
            value = max(0.0, min(1.0, fn(world, eid)))
            score *= value
            if score == 0.0:
                break
        return score

    def select_action(
        self, selector_name: str, world: World, eid: int
    ) -> tuple[str, float]:
        """Select the highest-scoring action from a utility selector.

        Returns (action_name, score). Returns ("", 0.0) if no actions.
        """
        action_names = self._utility_selectors.get(selector_name)
        if not action_names:
            return ("", 0.0)
        best_name = ""
        best_score = -1.0
        for name in action_names:
            s = self.score_action(name, world, eid)
            if s > best_score:
                best_score = s
                best_name = name
        if best_score < 0.0:
            return ("", 0.0)
        return (best_name, best_score)

    def utility_selector(self, name: str) -> list[str] | None:
        """Look up a utility selector's action list."""
        return self._utility_selectors.get(name)

    # --- Validation ---

    def _validate_tree(
        self, root_id: str, nodes: dict[str, Node]
    ) -> None:
        """Validate that all referenced node IDs exist in the graph."""
        if root_id not in nodes:
            raise ValueError(f"Root node '{root_id}' not found in nodes")
        for node_id, node in nodes.items():
            if node.id != node_id:
                raise ValueError(
                    f"Node key '{node_id}' does not match node.id '{node.id}'"
                )
            children = _node_children(node)
            for child_id in children:
                if child_id not in nodes:
                    raise ValueError(
                        f"Node '{node_id}' references unknown child '{child_id}'"
                    )


def _node_children(node: Node) -> tuple[str, ...]:
    """Extract child IDs from any node type."""
    if isinstance(node, (Action, Condition)):
        return ()
    if isinstance(node, (Sequence, Selector, Parallel, UtilitySelector)):
        return node.children
    if isinstance(node, (Inverter, Repeater, Succeeder, AlwaysFail)):
        return (node.child,) if node.child else ()
    return ()
