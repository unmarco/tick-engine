# tick-engine — Minimal Tick Engine Ecosystem

## Project Summary

A uv workspace monorepo containing the tick engine and all its extension packages. The tick engine is a minimal, general-purpose tick engine in Python — the skeleton of a game loop stripped of everything game-specific.

## Current Status

- **Version**: 0.1.1
- **Tests**: 574 passing across all 8 packages
- **Repository**: https://github.com/unmarco/tick-engine

## Workspace Structure

```
tick-engine/
├── pyproject.toml              # workspace root (virtual, not a package)
├── uv.lock                     # single lockfile (committed)
├── packages/
│   ├── tick/                   # core engine
│   ├── tick-colony/            # colony builder primitives
│   ├── tick-schedule/          # timers and periodic triggers
│   ├── tick-fsm/               # finite state machines
│   ├── tick-blueprint/         # entity templates
│   ├── tick-signal/            # in-process event bus
│   ├── tick-tween/             # value interpolation
│   └── tick-spatial/           # spatial indexing + pathfinding
```

## Packages

| Package | Import | Version | Description |
|---------|--------|---------|-------------|
| tick | `tick` | 0.2.1 | Core engine: loop, clock, world, systems |
| tick-colony | `tick_colony` | 0.1.0 | Colony builder / roguelike simulation primitives |
| tick-schedule | `tick_schedule` | 0.1.0 | Countdown timers and periodic triggers |
| tick-fsm | `tick_fsm` | 0.1.0 | Declarative finite state machines |
| tick-blueprint | `tick_blueprint` | 0.1.0 | Entity template registry |
| tick-signal | `tick_signal` | 0.1.0 | In-process pub/sub event bus |
| tick-tween | `tick_tween` | 0.1.0 | Value interpolation with easing |
| tick-spatial | `tick_spatial` | 0.1.0 | Grid2D, HexGrid, A* pathfinding |

## Technical Decisions

- **Language**: Python 3.11+
- **Dependencies**: stdlib only (no external deps for any package)
- **Package manager**: uv (workspace mode)
- **Build system**: hatchling
- **Dependency resolution**: workspace sources (`tick = { workspace = true }`)

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
```

## Dependency Graph

All extensions depend only on `tick>=0.2.1`. No extension depends on any other extension.

```
tick >= 0.2.1
  ├── tick-colony
  ├── tick-schedule
  ├── tick-fsm
  ├── tick-blueprint
  ├── tick-signal
  ├── tick-tween
  └── tick-spatial
```
