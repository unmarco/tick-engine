# tick-engine — Minimal Tick Engine Ecosystem

## Project Summary

A uv workspace monorepo containing the tick engine and all its extension packages. The tick engine is a minimal, general-purpose tick engine in Python — the skeleton of a game loop stripped of everything game-specific.

## Current Status

- **Version**: 0.14.0
- **Tests**: 1544 passing across all 16 packages
- **CI**: GitHub Actions (Python 3.11/3.12/3.13 matrix + mypy)
- **Type checking**: mypy strict mode, all packages pass
- **Repository**: https://github.com/unmarco/tick-engine

## Workspace Structure

```
tick-engine/
├── pyproject.toml              # workspace root (virtual, not a package)
├── uv.lock                     # single lockfile (committed)
├── .github/workflows/test.yml  # CI pipeline
├── packages/
│   ├── tick/                   # core engine
│   ├── tick-colony/            # colony builder primitives
│   ├── tick-schedule/          # timers and periodic triggers
│   ├── tick-fsm/               # finite state machines
│   ├── tick-blueprint/         # entity templates
│   ├── tick-signal/            # in-process event bus
│   ├── tick-tween/             # value interpolation
│   ├── tick-spatial/           # spatial indexing + pathfinding
│   ├── tick-event/            # world-level event scheduling
│   ├── tick-atlas/            # cell/tile property maps
│   ├── tick-ability/          # player-triggered abilities
│   ├── tick-command/          # typed command queue
│   ├── tick-resource/         # typed resource inventories
│   ├── tick-physics/          # kinematics + collision detection
│   ├── tick-ai/              # behavior trees + utility AI + blackboard
│   └── tick-llm/             # async LLM strategic layer
```

## Packages

| Package | Import | Version | Description |
|---------|--------|---------|-------------|
| tick | `tick` | 0.3.0 | Core engine: loop, clock, world, systems, query filters, hooks |
| tick-colony | `tick_colony` | 0.4.1 | Colony builder / roguelike simulation primitives |
| tick-schedule | `tick_schedule` | 0.1.0 | Countdown timers and periodic triggers |
| tick-fsm | `tick_fsm` | 0.2.0 | Declarative finite state machines (hierarchical) |
| tick-blueprint | `tick_blueprint` | 0.2.0 | Entity template registry (with meta) |
| tick-signal | `tick_signal` | 0.1.0 | In-process pub/sub event bus |
| tick-tween | `tick_tween` | 0.1.0 | Value interpolation with easing |
| tick-spatial | `tick_spatial` | 0.2.0 | Grid2D, Grid3D, HexGrid, A* pathfinding |
| tick-event | `tick_event` | 0.1.0 | World-level event scheduling (cycles, probabilistic events) |
| tick-atlas | `tick_atlas` | 0.2.0 | Cell/tile property maps (terrain, movement cost, passability) |
| tick-ability | `tick_ability` | 0.1.0 | Player-triggered abilities (charges, cooldowns, effects) |
| tick-command | `tick_command` | 0.1.0 | Typed command queue (handlers, footprints) |
| tick-resource | `tick_resource` | 0.1.0 | Typed resource inventories (recipes, decay) |
| tick-physics | `tick_physics` | 0.1.0 | N-dimensional kinematics and collision detection |
| tick-ai | `tick_ai` | 0.1.0 | Behavior trees, utility AI, and blackboard |
| tick-llm | `tick_llm` | 0.1.0 | Async LLM strategic layer (roles, parsers, thread pool) |

## Versioning Strategy

**Independent versioning** — each package versions separately. Bumped only when it changes.

- Workspace root version tracks release milestones (informational only)
- Core (`tick`) and extensions version independently
- Breaking changes bump the minor version (pre-1.0 semver)

## Technical Decisions

- **Language**: Python 3.11+
- **Dependencies**: stdlib only (no external deps for any package)
- **Package manager**: uv (workspace mode)
- **Build system**: hatchling
- **Dependency resolution**: workspace sources (`tick = { workspace = true }`)
- **Type checking**: mypy strict mode (all packages have `py.typed` markers)
- **CI**: GitHub Actions (test matrix + typecheck job)

## Development Practices

- **Git**: git-flow branching model (use `git flow` CLI commands)
- **Commits**: Conventional Commits (feat:, fix:, chore:, docs:, test:, refactor:)
- **Branching**: main, develop, feature/*, release/*, hotfix/*

## Running Tests

```bash
# All packages
uv run pytest

# Single package
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

# Type checking
uv run mypy
```

## Pygame Demos

| Demo | Packages | Description |
|------|----------|-------------|
| `examples/placement/` | tick, tick-command, tick-spatial, tick-atlas, tick-blueprint | Grid placement with blueprints and terrain |
| `examples/easing-gallery/` | tick, tick-tween, tick-fsm, tick-schedule, tick-signal | Easing function showcase |
| `examples/colony-sim/` | All 13 original packages | Colony builder visual chronicle |
| `examples/physics-sandbox/` | tick, tick-physics | Interactive 2D collision sandbox |
| `examples/ecosystem-arena/` | tick, tick-ai, tick-physics | Predator-prey ecosystem with BTs + utility AI |

### LLM Examples (requires LM Studio or compatible endpoint)

| Demo | Packages | Description |
|------|----------|-------------|
| `examples/llm-smoke/` | tick, tick-ai, tick-llm | Mock + LM Studio smoke tests with episodic memory |
| `examples/llm-roundtable/` | tick, tick-ai, tick-llm | Multi-agent structured debate (4 LLM agents, round-robin turns) |

All 16 packages have demo coverage.

```bash
# Run any demo
cd examples/<demo-name>
uv sync
uv run python main.py
```

## Dependency Graph

Extensions depend on `tick>=0.2.1`. tick-colony depends on all 11 extension packages.

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
  │     └── tick-resource >= 0.1.0
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
