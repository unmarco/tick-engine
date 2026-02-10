# tick-ai

Behavior trees, utility AI, and blackboard for the tick engine. Define behavior as composable tree nodes, score actions with utility considerations, and store per-entity knowledge in blackboards.

## Install

```bash
pip install tick-ai
```

```python
from tick_ai import AIManager, BehaviorTree, Blackboard, Status, make_bt_system
```

## Quick Start

```python
from tick import Engine
from tick_ai import (
    AIManager, Action, Condition, Sequence, Selector,
    BehaviorTree, Blackboard, Status,
    make_bt_system,
)

engine = Engine(tps=10, seed=42)
manager = AIManager()

# Register callbacks
manager.register_condition("is_hungry", lambda w, e: w.get(e, Blackboard).data.get("hunger", 0) > 50)
manager.register_action("eat", lambda w, c, e: Status.SUCCESS)
manager.register_action("idle", lambda w, c, e: Status.SUCCESS)

# Define tree
nodes = {
    "root": Selector(id="root", children=("hunt", "idle")),
    "hunt": Sequence(id="hunt", children=("hungry?", "eat")),
    "hungry?": Condition(id="hungry?", condition="is_hungry"),
    "eat": Action(id="eat", action="eat"),
    "idle": Action(id="idle", action="idle"),
}
manager.define_tree("survival", "root", nodes)

# Wire up
engine.add_system(make_bt_system(manager))
eid = engine.world.spawn()
engine.world.attach(eid, BehaviorTree(tree_name="survival"))
engine.world.attach(eid, Blackboard(data={"hunger": 80}))

engine.step()
bt = engine.world.get(eid, BehaviorTree)
assert bt.status == "success"
```

## API Reference

### AIManager

Central registry for tree definitions, action/condition/consideration callbacks, and utility selectors.

```python
manager = AIManager()
```

| Method | Description |
|--------|-------------|
| `define_tree(name, root_id, nodes)` | Register a BT definition; validates the node graph |
| `tree(name)` | Look up `(root_id, nodes)` or `None` |
| `register_action(name, fn)` | Register `(World, TickContext, eid) -> Status` |
| `register_condition(name, fn)` | Register `(World, eid) -> bool` |
| `register_consideration(name, fn)` | Register `(World, eid) -> float` (0.0-1.0) |
| `define_utility_action(name, considerations)` | Define a scored action |
| `define_utility_selector(name, action_names)` | Group actions into a selector |
| `score_action(name, world, eid)` | Multiplicative score for a utility action |
| `select_action(selector, world, eid)` | Pick highest-scoring action -> `(name, score)` |

### Components

| Component | Fields | Description |
|-----------|--------|-------------|
| `BehaviorTree` | `tree_name, running_node, status, repeat_counts` | Assigns a BT to an entity |
| `Blackboard` | `data: dict[str, Any]` | Per-entity key-value store |
| `UtilityAgent` | `selector_name, selected_action, score` | Assigns a utility selector to an entity |

### Systems

```python
make_bt_system(manager, on_status=None) -> System
make_utility_system(manager, on_select=None) -> System
```

- `on_status(world, ctx, eid, status_value)` -- called when a tree completes (SUCCESS or FAILURE)
- `on_select(world, ctx, eid, action_name, score)` -- called after each utility selection

### Node Types

| Node | Type | Description |
|------|------|-------------|
| `Action(id, action)` | Leaf | Calls registered callback -> Status |
| `Condition(id, condition)` | Leaf | Calls registered guard -> SUCCESS/FAILURE |
| `Sequence(id, children)` | Composite | All must succeed, fails fast |
| `Selector(id, children)` | Composite | First success wins, fallback chain |
| `Parallel(id, children, policy)` | Composite | Runs all children; `require_all` or `require_one` |
| `UtilitySelector(id, children)` | Composite | Scores Action children, runs highest |
| `Inverter(id, child)` | Decorator | Flips SUCCESS/FAILURE |
| `Repeater(id, child, max_count, fail_policy)` | Decorator | Repeats N times; `fail` or `restart` on failure |
| `Succeeder(id, child)` | Decorator | Always SUCCESS (unless RUNNING) |
| `AlwaysFail(id, child)` | Decorator | Always FAILURE (unless RUNNING) |

All nodes are frozen dataclasses. Children are referenced by string ID, forming a flat `dict[str, Node]` graph.

## Utility AI

```python
from tick_ai import AIManager, UtilityAgent, curves, make_utility_system

manager = AIManager()

# Register considerations (return 0.0-1.0)
manager.register_consideration("hunger", lambda w, e: 0.8)
manager.register_consideration("safety", lambda w, e: 0.3)

# Define utility actions with their considerations
manager.define_utility_action("eat", ["hunger"])
manager.define_utility_action("flee", ["safety"])

# Group into a selector
manager.define_utility_selector("decide", ["eat", "flee"])

# Use with ECS
engine.add_system(make_utility_system(manager))
eid = engine.world.spawn()
engine.world.attach(eid, UtilityAgent(selector_name="decide"))
```

Scoring is multiplicative: each consideration returns 0.0-1.0, values are multiplied together. Short-circuits on 0.0.

## Response Curves

Five built-in curves for shaping consideration outputs:

```python
from tick_ai.curves import linear, quadratic, logistic, inverse, step

linear(0.5)              # 0.5
quadratic(0.5, exp=2.0)  # 0.25
logistic(0.5, k=10.0)    # ~0.5
inverse(0.5)             # 0.5
step(0.3, threshold=0.5) # 0.0
```

All accept a float in [0.0, 1.0] and return a float in [0.0, 1.0]. Input is clamped.

## RUNNING Resumption

When an Action returns `RUNNING`, the tree records which node is running. On the next tick, composite nodes (Sequence, Selector) skip children before the running child and resume directly from it. Parallel nodes always run all children regardless.

## See Also

For simpler state modeling (UI states, game phases, entity modes), see [tick-fsm](../tick-fsm/).

## Part of [tick-engine](../../README.md)

MIT License
