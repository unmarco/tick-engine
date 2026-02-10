# easing-gallery

Interactive easing curve visualizer with comparison and sandbox modes. Exercises tick-tween, tick-fsm, tick-schedule, and tick-signal.

## Packages Used

- **tick** -- engine, ECS, systems
- **tick-tween** -- value interpolation with easing functions
- **tick-fsm** -- state machine driving orb lifecycle (active / completed)
- **tick-schedule** -- auto-wave timer for periodic launches
- **tick-signal** -- pub/sub for completion events

## Controls

| Key | Action |
|-----|--------|
| Space | Launch wave (comparison) / spawn orb at center (sandbox) |
| Tab | Toggle comparison / sandbox mode |
| 1-4 | Select easing function (sandbox mode) |
| A | Toggle auto-wave timer |
| +/- | Adjust tween duration |
| C | Clear all orbs |
| Click | Spawn orb at cursor (sandbox mode) |
| Esc | Quit |

## Run

```bash
cd examples/easing-gallery
uv sync
uv run python main.py
```

---

Part of [tick-engine](../../README.md).
