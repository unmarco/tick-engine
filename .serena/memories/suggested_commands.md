# Essential Commands for tick-engine Development

## Setup & Sync
```bash
# Initial setup - install all packages
uv sync

# Sync with all optional packages
uv sync --all-packages
```

## Testing
```bash
# Run ALL tests (1644 tests across 16 packages)
uv run pytest

# Verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x

# Test specific package
uv run --package tick pytest
uv run --package tick-colony pytest
uv run --package tick-spatial pytest
# ... (all 16 packages available)
```

## Type Checking
```bash
# Type check all packages (mypy strict mode)
uv run mypy

# Type check specific package directory
uv run mypy packages/tick
```

## Git Workflow (git-flow)
```bash
# Feature development
git flow feature start <feature-name>
git flow feature finish <feature-name>

# Release process
git flow release start X.Y.Z
# ... make version changes ...
GIT_MERGE_AUTOEDIT=no git flow release finish X.Y.Z -m "Release X.Y.Z"
git push origin main develop --tags

# Create GitHub release
gh release create X.Y.Z --title "vX.Y.Z" --notes "..."
```

## Running Examples
```bash
# Pygame demos
cd examples/placement    # or easing-gallery, colony-sim, physics-sandbox, ecosystem-arena
uv sync
uv run python main.py

# LLM examples
cd examples/llm-smoke    # or llm-roundtable
uv sync
uv run python main.py

# Chronicle demo with LLM (from workspace root)
uv run --package tick-colony python -m examples.chronicle --mock
```

## Linux System Commands
Standard Linux/Unix commands work normally:
- `ls`, `cd`, `pwd` - navigation
- `grep`, `find` - searching
- `cat`, `head`, `tail` - file viewing
- `git` - version control
