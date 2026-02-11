# tick-engine: Code Style & Conventions

## Python Conventions
- **Style**: PEP 8 compliant
- **Type Hints**: Required on all function signatures
- **Docstrings**: Google-style for all public APIs
- **Naming**:
  - `snake_case` - functions, methods, variables, modules
  - `PascalCase` - classes
  - `UPPER_CASE` - constants

## Component Design (Critical Rules)
1. **Must be dataclasses**: All components use `@dataclass`
2. **No nested dataclasses**: Components cannot contain nested dataclasses (breaks serialization)
3. **Frozen when appropriate**: Use `frozen=True` for immutable types
4. **Type hints required**: All component fields must be typed

Example:
```python
from dataclasses import dataclass

@dataclass
class Health:
    value: int
    max_value: int

# WRONG - nested dataclass breaks serialization
@dataclass  
class Position:
    coords: Coord  # If Coord is also a dataclass, this breaks
```

## System Design
- **Signature**: `(World, TickContext) -> None`
- **Pure functions**: No hidden state
- **Deterministic**: Same inputs = same outputs
- **Side effects**: Only modify world state

## Testing
- **Location**: `packages/<name>/tests/`
- **Naming**: `test_*.py` files, `test_*` functions
- **Pattern**: Arrange-Act-Assert
- **Isolation**: No test interdependencies

## Import Names (Critical!)
Package names use hyphens, imports use underscores:
- `tick-colony` → `from tick_colony import ...`
- `tick-spatial` → `from tick_spatial import ...`
- `tick-fsm` → `from tick_fsm import ...`

## Commit Messages (Conventional Commits)
```
feat(package): Add new feature
fix(package): Fix bug
chore(package): Maintenance
docs(package): Documentation
test(package): Add tests
refactor(package): Restructure code
```

## Type Checking
- **Mode**: mypy strict
- **Required**: All packages must pass
- **Markers**: All packages include `py.typed`

## Key Patterns
- **Snapshot/Restore**: Serialization support required
- **Hooks**: Use `world.on_attach/on_detach`
- **Query Filters**: `Not()`, `AnyOf()` for advanced queries
