# tick-engine: Tech Stack

## Core Technologies
- **Language**: Python 3.11+ (required)
- **Package Manager**: uv (workspace mode)
- **Build System**: hatchling
- **Dependencies**: stdlib only (NO external deps)

## Development Tools
- **Testing**: pytest (1644 tests across 16 packages)
- **Type Checking**: mypy (strict mode, all packages)
- **CI/CD**: GitHub Actions
  - Python 3.11, 3.12, 3.13 matrix
  - pytest + mypy jobs

## Repository Structure
- **Type**: uv workspace monorepo
- **Packages**: 16 independent packages
- **Versioning**: Independent (each package versions separately)
- **Git Flow**: git-flow branching model

## Package Build
- All packages use hatchling
- All packages include `py.typed` marker
- Workspace dependencies: `tick = { workspace = true }`
- Single committed lockfile: `uv.lock`

## CI Matrix
```yaml
Python versions: 3.11, 3.12, 3.13
Jobs:
  - pytest (all tests)
  - mypy (strict type checking)
```

## Key Constraints
- **NO external dependencies** (stdlib only)
- **Type-safe** (mypy strict mode)
- **Python 3.11+** (uses modern features)
- **Deterministic** (same seed = same results)
