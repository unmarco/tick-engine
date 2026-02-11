# What to Do When a Task is Completed

## Standard Completion Checklist

### 1. Run Tests
```bash
uv run pytest
```
**Must pass**: All 1644 tests across 16 packages

### 2. Type Check
```bash
uv run mypy
```
**Must pass**: Success: no issues found

### 3. Verify Examples (if modified)
```bash
cd examples/<relevant-example>
uv sync
uv run python main.py
```
**Must**: Run without errors

### 4. Update Documentation (if public API changed)
- Package README.md
- CLAUDE.md (if dev practices changed)
- Root README.md (if new package/major feature)

### 5. Commit Changes
```bash
git add <files>
git commit -m "feat(package): description

- Detail 1
- Detail 2

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## Release Completion Checklist

### 1. Version Bumps
- Update package `pyproject.toml` version
- Update workspace `pyproject.toml` version
- Sync dependencies: `uv sync`

### 2. Final Verification
```bash
uv run pytest    # All tests pass
uv run mypy      # Type checking pass
```

### 3. Git Flow Release
```bash
git flow release start X.Y.Z
# ... make changes ...
git commit -m "chore: bump workspace to X.Y.Z"
GIT_MERGE_AUTOEDIT=no git flow release finish X.Y.Z -m "Release X.Y.Z"
git push origin main develop --tags
```

### 4. GitHub Release
```bash
gh release create X.Y.Z --title "vX.Y.Z" --notes "Release notes"
```

## Quality Gates (All Must Pass)
- ✅ All 1644 tests pass
- ✅ mypy strict mode passes
- ✅ No external dependencies added
- ✅ Components are dataclasses (not nested)
- ✅ Public APIs have docstrings
- ✅ Examples run if modified
- ✅ Conventional commit format used
