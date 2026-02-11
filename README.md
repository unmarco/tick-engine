# tick-engine

A minimal, general-purpose tick engine ecosystem in Python. This is the skeleton of a game loop stripped of everything game-specific -- entities, components, systems, a fixed-timestep clock, and nothing else. Built as an educational project to understand the tick pattern from first principles.

The engine and all extensions use only the Python standard library. No external dependencies.

## Packages

| Package | Import | Version | Description |
|---------|--------|---------|-------------|
| [tick](packages/tick/) | `tick` | 0.3.0 | Core engine: loop, clock, world, systems, query filters, hooks |
| [tick-colony](packages/tick-colony/) | `tick_colony` | 0.4.1 | Colony builder / roguelike simulation primitives |
| [tick-schedule](packages/tick-schedule/) | `tick_schedule` | 0.1.0 | Countdown timers and periodic triggers |
| [tick-fsm](packages/tick-fsm/) | `tick_fsm` | 0.2.0 | Declarative finite state machines (hierarchical) |
| [tick-blueprint](packages/tick-blueprint/) | `tick_blueprint` | 0.2.0 | Entity template registry (with meta) |
| [tick-signal](packages/tick-signal/) | `tick_signal` | 0.1.0 | In-process pub/sub event bus |
| [tick-tween](packages/tick-tween/) | `tick_tween` | 0.1.0 | Value interpolation with easing |
| [tick-spatial](packages/tick-spatial/) | `tick_spatial` | 0.2.0 | Grid2D, Grid3D, HexGrid, A* pathfinding |
| [tick-event](packages/tick-event/) | `tick_event` | 0.1.0 | World-level event scheduling (cycles, probabilistic events) |
| [tick-atlas](packages/tick-atlas/) | `tick_atlas` | 0.2.0 | Cell/tile property maps (terrain, movement cost, passability) |
| [tick-ability](packages/tick-ability/) | `tick_ability` | 0.1.0 | Player-triggered abilities (charges, cooldowns, effects) |
| [tick-command](packages/tick-command/) | `tick_command` | 0.1.0 | Typed command queue (handlers, footprints) |
| [tick-resource](packages/tick-resource/) | `tick_resource` | 0.1.0 | Typed resource inventories (recipes, decay) |
| [tick-physics](packages/tick-physics/) | `tick_physics` | 0.1.0 | N-dimensional kinematics and collision detection |
| [tick-ai](packages/tick-ai/) | `tick_ai` | 0.1.0 | Behavior trees, utility AI, and blackboard |
| [tick-llm](packages/tick-llm/) | `tick_llm` | 0.1.0 | Async LLM strategic layer (roles, parsers, thread pool) |

## Quick Start

```bash
# Clone and set up the workspace
cd tick-engine
uv sync
```

```python
from dataclasses import dataclass
from tick import Engine, World
from tick.types import TickContext

@dataclass
class Health:
    value: int

def print_health(world: World, ctx: TickContext) -> None:
    for eid, (hp,) in world.query(Health):
        print(f"[tick {ctx.tick_number}] entity {eid} hp={hp.value}")

engine = Engine(tps=10)
e = engine.world.spawn()
engine.world.attach(e, Health(value=100))
engine.add_system(print_health)
engine.run(3)
```

Output:

```
[tick 1] entity 0 hp=100
[tick 2] entity 0 hp=100
[tick 3] entity 0 hp=100
```

## Dependency Graph

Extensions depend on `tick>=0.2.1`. tick-colony depends on all extension packages. tick-atlas depends on tick-spatial. tick-llm depends on tick-ai. Mix and match freely.

```
tick >= 0.2.1
  ├── tick-colony >= 0.4.1
  │     ├── tick-spatial >= 0.2.0
  │     ├── tick-schedule >= 0.1.0
  │     ├── tick-fsm >= 0.1.0
  │     ├── tick-blueprint >= 0.1.0
  │     ├── tick-signal >= 0.1.0
  │     ├── tick-event >= 0.1.0
  │     ├── tick-command >= 0.1.0
  │     ├── tick-atlas >= 0.2.0
  │     ├── tick-ability >= 0.1.0
  │     ├── tick-resource >= 0.1.0
  │     ├── tick-ai >= 0.1.0
  │     └── tick-llm >= 0.1.0
  ├── tick-schedule
  ├── tick-fsm
  ├── tick-blueprint
  ├── tick-signal
  ├── tick-tween
  ├── tick-spatial
  ├── tick-event
  ├── tick-atlas >= 0.2.0
  │     └── tick-spatial >= 0.2.0
  ├── tick-ability >= 0.1.0
  ├── tick-command >= 0.1.0
  ├── tick-resource >= 0.1.0
  ├── tick-physics >= 0.1.0
  ├── tick-ai >= 0.1.0
  └── tick-llm >= 0.1.0
        └── tick-ai >= 0.1.0
```

## Examples

| Example | Packages | Description |
|---------|----------|-------------|
| [placement](examples/placement/) | tick, tick-command, tick-spatial, tick-atlas, tick-blueprint | Tile placement playground |
| [easing-gallery](examples/easing-gallery/) | tick, tick-tween, tick-fsm, tick-schedule, tick-signal | Easing function gallery |
| [colony-sim](examples/colony-sim/) | all packages | Colony simulation chronicle |
| [physics-sandbox](examples/physics-sandbox/) | tick, tick-physics | Interactive 2D physics sandbox |
| [ecosystem-arena](examples/ecosystem-arena/) | tick, tick-ai, tick-physics | Predator-prey ecosystem |
| [llm-smoke](examples/llm-smoke/) | tick, tick-ai, tick-llm | Mock + LM Studio smoke tests |
| [llm-roundtable](examples/llm-roundtable/) | tick, tick-ai, tick-llm | Multi-agent structured debate |

Pygame examples are standalone apps. Run with `uv run python main.py` from the example directory. The chronicle demo also supports LLM agents: `uv run --package tick-colony python -m examples.chronicle --mock`.

## Development

This is a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/) monorepo with [hatchling](https://hatch.pypa.io/) as the build backend.

```bash
# Install all packages in development mode
uv sync

# Run all tests
uv run pytest

# Run tests for a single package
uv run --package tick pytest
uv run --package tick-colony pytest
uv run --package tick-schedule pytest
uv run --package tick-fsm pytest
uv run --package tick-blueprint pytest
uv run --package tick-signal pytest
uv run --package tick-tween pytest
uv run --package tick-spatial pytest
uv run --package tick-event pytest
uv run --package tick-atlas pytest
uv run --package tick-ability pytest
uv run --package tick-command pytest
uv run --package tick-resource pytest
uv run --package tick-physics pytest
uv run --package tick-ai pytest
uv run --package tick-llm pytest
```

Requires Python 3.11+.

## License

MIT
