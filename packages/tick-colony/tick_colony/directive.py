"""Directive parser factory for structured LLM responses.

Translates JSON responses containing ``"directives"`` into typed handler calls.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from tick_ai.components import Blackboard
from tick_llm.parsers import strip_code_fences

DirectiveHandler = Callable[[dict[str, Any]], None]


def make_directive_parser(
    handlers: dict[str, DirectiveHandler],
    *,
    fallback: DirectiveHandler | None = None,
    write_strategy: bool = True,
) -> Callable[[str, Blackboard], None]:
    """Return a ``ParserFn`` that dispatches directives to typed handlers.

    Expected LLM response format::

        {
            "directives": [
                {"type": "assign_task", "entity": 5, "task": "gather_wood"},
                {"type": "set_priority", "resource": "food", "level": "high"}
            ],
            "reasoning": "Food supplies are low...",
            "confidence": 0.85
        }

    Each directive's ``"type"`` is looked up in *handlers*. Unknown types go to
    *fallback* if provided, otherwise they are skipped.

    If *write_strategy* is True (default), the full parsed dict is
    shallow-merged into ``blackboard.data["strategy"]``.

    If no ``"directives"`` key is present, falls back to the same behaviour as
    ``default_json_parser`` (just writes strategy).
    """

    def _parse(response: str, blackboard: Blackboard) -> None:
        cleaned = strip_code_fences(response)
        parsed: Any = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError(
                f"Expected JSON object, got {type(parsed).__name__}"
            )

        directives = parsed.get("directives")
        if isinstance(directives, list):
            for entry in directives:
                if not isinstance(entry, dict):
                    continue
                dtype = entry.get("type")
                if dtype is None:
                    continue
                handler = handlers.get(dtype)
                if handler is not None:
                    handler(entry)
                elif fallback is not None:
                    fallback(entry)

        if write_strategy:
            strategy: dict[str, Any] = blackboard.data.setdefault("strategy", {})
            strategy.update(parsed)

    return _parse
