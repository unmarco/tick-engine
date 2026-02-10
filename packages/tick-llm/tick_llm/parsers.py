"""Response parsers for LLM output."""
from __future__ import annotations

import json
import re
from typing import Any

from tick_ai.components import Blackboard

# Pattern to match ```json ... ``` or ``` ... ``` code fences.
_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL,
)


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences wrapping the text.

    Handles both ``\\`\\`\\`json ... \\`\\`\\``` and ``\\`\\`\\` ... \\`\\`\\```
    wrapping. Returns the inner content if fences are found, otherwise returns
    the original text unchanged.
    """
    match = _CODE_FENCE_RE.match(text)
    if match:
        return match.group(1)
    return text


def default_json_parser(response: str, blackboard: Blackboard) -> None:
    """Parse an LLM response as JSON and merge into the Blackboard.

    Strips markdown code fences, parses the response as JSON, expects a
    top-level dict, and shallow-merges all key-value pairs into
    ``blackboard.data["strategy"]``.

    Raises:
        ValueError: If the parsed JSON is not a dict.
        json.JSONDecodeError: If the response is not valid JSON.
    """
    cleaned = strip_code_fences(response)
    parsed: Any = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Expected JSON object, got {type(parsed).__name__}"
        )
    strategy: dict[str, Any] = blackboard.data.setdefault("strategy", {})
    strategy.update(parsed)
