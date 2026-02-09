# colony-sim

Visual colony simulation chronicle exercising all 13 original tick-engine packages. Watch colonists autonomously forage, rest, and build while seasons cycle and world events unfold.

## Packages Used

All 13 packages: tick, tick-colony, tick-schedule, tick-fsm, tick-blueprint, tick-signal, tick-tween, tick-spatial, tick-event, tick-atlas, tick-ability, tick-command, tick-resource.

## Controls

| Key | Action |
|-----|--------|
| Space | Pause / resume |
| 1-4 | Speed (0.5x / 1x / 2x / 4x) |
| F1 | Food Drop ability |
| F2 | Rally ability |
| F3 | Shelter ability |
| Left-click | Select colonist (click empty to deselect) |
| Right-click | Move selected colonist to tile |
| Esc | Quit |

## CLI Flags

```
--seed N       Random seed (default: 42)
--pop N        Starting population, 2-16 (default: 8)
--map-size N   Grid width/height, 12-40 (default: 20)
--tps N        Ticks per second (default: 10)
--chronicle F  Save JSONL chronicle to file on quit
```

## Run

```bash
cd examples/colony-sim
uv sync
uv run python main.py
```

---

Part of [tick-engine](../../README.md).
