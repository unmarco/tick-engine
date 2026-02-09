# tick-command

Typed command queue for the tick engine. Routes external input (player, AI, network) to handlers within the tick loop. FIFO ordering, deterministic processing, typed dispatch.

## Install

```bash
pip install tick-command
```

```python
from tick_command import CommandQueue, make_command_system, expand_footprint, resolve_footprint
```

## Quick Example

```python
from dataclasses import dataclass
from tick import Engine, World
from tick.types import TickContext
from tick_command import CommandQueue, make_command_system

@dataclass(frozen=True)
class PlaceStructure:
    name: str
    x: int
    y: int

engine = Engine(tps=10)
queue = CommandQueue()

# Register typed handler
def place_handler(cmd: PlaceStructure, world: World, ctx: TickContext) -> bool:
    print(f"[tick {ctx.tick_number}] placing {cmd.name} at ({cmd.x}, {cmd.y})")
    return True  # accepted

queue.handle(PlaceStructure, place_handler)

# System processes queue during tick
engine.add_system(make_command_system(queue,
    on_accept=lambda cmd: print(f"accepted: {cmd}"),
    on_reject=lambda cmd: print(f"rejected: {cmd}"),
))

# External code enqueues commands (between ticks, from UI/AI/network)
queue.enqueue(PlaceStructure("farm", 5, 3))
engine.run(1)
```

## API Reference

### CommandQueue

```python
queue = CommandQueue()
```

| Method | Description |
|--------|-------------|
| `.handle(cmd_type, handler)` | Register handler for a command type. `handler(cmd, world, ctx) -> bool`. |
| `.enqueue(cmd)` | Add command to the queue. Safe to call between ticks. |
| `.pending() -> int` | Number of commands waiting. |
| `.drain(world, ctx) -> list[(cmd, bool)]` | Process all pending commands. Raises `TypeError` if no handler. |

Commands are user-defined frozen dataclasses -- the engine imposes no base class. One handler per command class; later calls overwrite.

### make_command_system

```python
make_command_system(
    queue: CommandQueue,
    on_accept=None,  # (cmd) -> None
    on_reject=None,  # (cmd) -> None
) -> System
```

Returns a system that drains the queue each tick. `on_accept` fires after a handler returns `True`; `on_reject` fires after `False`.

### Footprint Utilities

Coord math for multi-tile placement. N-dimensional, compatible with tick-spatial's `Coord` type.

#### expand_footprint

```python
expand_footprint(origin, dimensions) -> list[Coord]
```

Expand a rectangular footprint from `origin` with `dimensions`.

```python
expand_footprint((5, 3), (2, 2))
# [(5, 3), (5, 4), (6, 3), (6, 4)]

expand_footprint((0, 0, 0), (2, 1, 2))  # 3D works too
# [(0, 0, 0), (0, 0, 1), (1, 0, 0), (1, 0, 1)]
```

#### resolve_footprint

```python
resolve_footprint(origin, shape) -> list[Coord]
```

Normalize either form to absolute coordinates:

```python
# Dimensions tuple -> rectangular expansion
resolve_footprint((5, 3), (2, 3))

# Offset list -> translate relative to origin
resolve_footprint((5, 3), [(0, 0), (1, 0), (2, 0), (1, 1)])
# [(5, 3), (6, 3), (7, 3), (6, 4)]
```

## Design Decisions

- **FIFO ordering** -- priority is a game concern, not an engine concern
- **Deterministic** -- commands processed at a known point in the tick cycle
- **Typed dispatch** -- one handler per command class, mypy-strict friendly
- **Game-agnostic** -- the queue routes dataclasses to handlers, nothing more
- **Handler returns `bool`** -- simplest contract; games layer richer feedback on top

## Part of [tick-engine](../../README.md)

MIT License
