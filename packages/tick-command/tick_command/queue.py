"""CommandQueue — typed command routing with FIFO ordering."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from tick import TickContext, World


class CommandQueue:
    """Routes external commands to typed handlers during the tick loop.

    Commands are user-defined frozen dataclasses — the engine imposes no base
    class.  One handler per command class, dispatched by type.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Any], Callable[..., bool]] = {}
        self._pending: deque[Any] = deque()

    def handle(
        self,
        cmd_type: type[Any],
        handler: Callable[..., bool],
    ) -> None:
        """Register a handler for a command type.

        ``handler(cmd, world, ctx) -> bool`` — return True to accept, False to
        reject.  Only one handler per type; later calls overwrite.
        """
        self._handlers[cmd_type] = handler

    def enqueue(self, cmd: Any) -> None:
        """Add a command to the queue.  Safe to call between ticks."""
        self._pending.append(cmd)

    def pending(self) -> int:
        """Return the number of commands waiting to be processed."""
        return len(self._pending)

    def drain(
        self,
        world: World,
        ctx: TickContext,
    ) -> list[tuple[Any, bool]]:
        """Process all pending commands.  Returns ``[(cmd, accepted), ...]``.

        Raises ``TypeError`` if no handler is registered for a command's type.
        """
        results: list[tuple[Any, bool]] = []
        while self._pending:
            cmd = self._pending.popleft()
            cmd_type = type(cmd)
            handler = self._handlers.get(cmd_type)
            if handler is None:
                raise TypeError(
                    f"No handler registered for {cmd_type.__qualname__}"
                )
            accepted = handler(cmd, world, ctx)
            results.append((cmd, accepted))
        return results
