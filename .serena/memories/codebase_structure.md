# tick-engine: Codebase Structure

## Workspace Layout
```
tick-engine/              # Workspace root
├── pyproject.toml        # Workspace config
├── uv.lock              # Single lockfile (committed)
├── README.md            # User docs
├── CLAUDE.md            # Dev instructions
├── .github/workflows/   # CI/CD
├── .serena/            # Serena config
├── packages/           # All 16 packages
│   ├── tick/
│   ├── tick-colony/
│   ├── tick-schedule/
│   ├── tick-fsm/
│   ├── tick-blueprint/
│   ├── tick-signal/
│   ├── tick-tween/
│   ├── tick-spatial/
│   ├── tick-event/
│   ├── tick-atlas/
│   ├── tick-ability/
│   ├── tick-command/
│   ├── tick-resource/
│   ├── tick-physics/
│   ├── tick-ai/
│   └── tick-llm/
└── examples/           # Standalone demos
    ├── placement/
    ├── easing-gallery/
    ├── colony-sim/
    ├── physics-sandbox/
    ├── ecosystem-arena/
    ├── llm-smoke/
    └── llm-roundtable/
```

## Package Structure (Standard)
```
packages/<package-name>/
├── pyproject.toml       # Package metadata
├── README.md           # Package docs
├── <import_name>/      # Source code
│   ├── __init__.py    # Public API
│   ├── py.typed       # Type marker
│   └── *.py          # Implementation
└── tests/            # Tests
    └── test_*.py
```

## 16 Packages (Import Names)
1. `tick` - Core engine
2. `tick_colony` - Colony builder primitives
3. `tick_schedule` - Timers/periodic triggers
4. `tick_fsm` - Finite state machines
5. `tick_blueprint` - Entity templates
6. `tick_signal` - Event bus
7. `tick_tween` - Value interpolation
8. `tick_spatial` - Grids + pathfinding
9. `tick_event` - Event scheduling
10. `tick_atlas` - Tile property maps
11. `tick_ability` - Player abilities
12. `tick_command` - Command queue
13. `tick_resource` - Resource inventories
14. `tick_physics` - Kinematics + collision
15. `tick_ai` - Behavior trees + utility AI
16. `tick_llm` - Async LLM layer

## Dependencies
- Core: `tick` (no deps)
- Extensions: depend on `tick>=0.2.1`
- Colony: depends on all 13 extensions + tick-ai + tick-llm
- Atlas: depends on tick-spatial
- LLM: depends on tick-ai

## Critical Files
- `pyproject.toml` (root): Workspace config, pytest/mypy settings
- `uv.lock`: Committed for reproducible builds
- `CLAUDE.md`: Development context
- `.github/workflows/test.yml`: CI pipeline
- `.serena/project.yml`: Serena MCP config
