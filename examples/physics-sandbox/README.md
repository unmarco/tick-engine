# physics-sandbox

Interactive 2D physics sandbox demonstrating the tick-physics package.

## Packages Used

- **tick** -- engine, ECS, systems
- **tick-physics** -- KinematicBody, CircleCollider, AABBCollider, collision detection, vec math

## Controls

| Key | Action |
|-----|--------|
| Left-click | Spawn a circle |
| Right-click | Spawn an AABB |
| G | Toggle gravity |
| Space | Pause / resume |
| C | Clear all entities |
| Esc | Quit |

## Run

```bash
cd examples/physics-sandbox
uv sync
uv run python main.py
```

---

Part of [tick-engine](../../README.md).
