"""Tests for the directive parser factory."""
from __future__ import annotations

import json
from typing import Any

import pytest

from tick_ai.components import Blackboard
from tick_colony.directive import DirectiveHandler, make_directive_parser


class TestDirectiveDispatch:
    """Tests for directive type dispatch to handlers."""

    def test_basic_dispatch(self) -> None:
        """Single directive dispatched to matching handler."""
        received: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "assign_task": lambda d: received.append(d),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [{"type": "assign_task", "entity": 5}],
        })
        parser(response, bb)
        assert len(received) == 1
        assert received[0] == {"type": "assign_task", "entity": 5}

    def test_multiple_directives_dispatched_in_order(self) -> None:
        """Multiple directives dispatched in list order."""
        log: list[str] = []
        handlers: dict[str, DirectiveHandler] = {
            "build": lambda d: log.append(f"build-{d['target']}"),
            "move": lambda d: log.append(f"move-{d['target']}"),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [
                {"type": "build", "target": "wall"},
                {"type": "move", "target": "north"},
                {"type": "build", "target": "gate"},
            ],
        })
        parser(response, bb)
        assert log == ["build-wall", "move-north", "build-gate"]

    def test_handler_receives_full_directive_dict(self) -> None:
        """Handler receives the complete directive dict including type."""
        captured: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "set_priority": lambda d: captured.append(d),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        directive = {
            "type": "set_priority",
            "resource": "food",
            "level": "high",
            "urgency": 9,
        }
        response = json.dumps({"directives": [directive]})
        parser(response, bb)
        assert len(captured) == 1
        assert captured[0] == directive

    def test_empty_directives_list(self) -> None:
        """Empty directives list calls no handlers."""
        called = False

        def handler(_d: dict[str, Any]) -> None:
            nonlocal called
            called = True

        handlers: dict[str, DirectiveHandler] = {"x": handler}
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({"directives": []})
        parser(response, bb)
        assert not called


class TestUnknownDirectiveTypes:
    """Tests for unknown directive type handling."""

    def test_unknown_type_skipped_no_fallback(self) -> None:
        """Unknown directive type is silently skipped when no fallback."""
        received: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "known": lambda d: received.append(d),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [
                {"type": "unknown_thing", "data": 1},
                {"type": "known", "data": 2},
            ],
        })
        parser(response, bb)
        assert len(received) == 1
        assert received[0]["data"] == 2

    def test_unknown_type_goes_to_fallback(self) -> None:
        """Unknown directive type dispatched to fallback handler."""
        fallback_received: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "known": lambda d: None,
        }
        parser = make_directive_parser(
            handlers,
            fallback=lambda d: fallback_received.append(d),
            write_strategy=False,
        )
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [{"type": "mystery", "val": 42}],
        })
        parser(response, bb)
        assert len(fallback_received) == 1
        assert fallback_received[0] == {"type": "mystery", "val": 42}


class TestMalformedDirectiveEntries:
    """Tests for non-conforming entries in the directives list."""

    def test_non_dict_entry_skipped(self) -> None:
        """Non-dict items in directives list are skipped."""
        received: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "ok": lambda d: received.append(d),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [
                "not a dict",
                42,
                None,
                {"type": "ok", "x": 1},
            ],
        })
        parser(response, bb)
        assert len(received) == 1
        assert received[0] == {"type": "ok", "x": 1}

    def test_entry_missing_type_key_skipped(self) -> None:
        """Directive entry without a 'type' key is skipped."""
        received: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "valid": lambda d: received.append(d),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [
                {"no_type_here": True, "data": "abc"},
                {"type": "valid", "data": "def"},
            ],
        })
        parser(response, bb)
        assert len(received) == 1
        assert received[0]["data"] == "def"


class TestWriteStrategy:
    """Tests for strategy writing to Blackboard."""

    def test_write_strategy_true_merges(self) -> None:
        """write_strategy=True shallow-merges parsed dict into bb.data['strategy']."""
        handlers: dict[str, DirectiveHandler] = {}
        parser = make_directive_parser(handlers, write_strategy=True)
        bb = Blackboard(data={})
        response = json.dumps({
            "directives": [],
            "reasoning": "low on food",
            "confidence": 0.9,
        })
        parser(response, bb)
        assert "strategy" in bb.data
        assert bb.data["strategy"]["reasoning"] == "low on food"
        assert bb.data["strategy"]["confidence"] == 0.9
        assert bb.data["strategy"]["directives"] == []

    def test_write_strategy_false_no_write(self) -> None:
        """write_strategy=False does not write anything to bb.data."""
        handlers: dict[str, DirectiveHandler] = {}
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({"directives": [], "note": "test"})
        parser(response, bb)
        assert "strategy" not in bb.data

    def test_write_strategy_merges_into_existing(self) -> None:
        """Strategy merges into pre-existing bb.data['strategy'] dict."""
        handlers: dict[str, DirectiveHandler] = {}
        parser = make_directive_parser(handlers, write_strategy=True)
        bb = Blackboard(data={"strategy": {"old_key": "preserved"}})
        response = json.dumps({"new_key": "added"})
        parser(response, bb)
        assert bb.data["strategy"]["old_key"] == "preserved"
        assert bb.data["strategy"]["new_key"] == "added"

    def test_write_strategy_shallow_merge_overwrites(self) -> None:
        """Shallow merge overwrites existing keys in strategy."""
        handlers: dict[str, DirectiveHandler] = {}
        parser = make_directive_parser(handlers, write_strategy=True)
        bb = Blackboard(data={"strategy": {"priority": "low"}})
        response = json.dumps({"priority": "high"})
        parser(response, bb)
        assert bb.data["strategy"]["priority"] == "high"


class TestNoDirectivesKey:
    """Tests for responses without a 'directives' key."""

    def test_no_directives_key_writes_strategy(self) -> None:
        """Response without 'directives' key still writes strategy."""
        handlers: dict[str, DirectiveHandler] = {
            "x": lambda d: None,
        }
        parser = make_directive_parser(handlers, write_strategy=True)
        bb = Blackboard(data={})
        response = json.dumps({"plan": "gather resources", "score": 0.7})
        parser(response, bb)
        assert bb.data["strategy"]["plan"] == "gather resources"
        assert bb.data["strategy"]["score"] == 0.7

    def test_no_directives_key_no_handler_calls(self) -> None:
        """Response without 'directives' key calls no handlers."""
        called = False

        def handler(_d: dict[str, Any]) -> None:
            nonlocal called
            called = True

        handlers: dict[str, DirectiveHandler] = {"x": handler}
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = json.dumps({"plan": "idle"})
        parser(response, bb)
        assert not called


class TestCodeFences:
    """Tests for code-fenced JSON responses."""

    def test_json_code_fence_stripped(self) -> None:
        """Response wrapped in ```json ... ``` code fence is parsed."""
        received: list[dict[str, Any]] = []
        handlers: dict[str, DirectiveHandler] = {
            "act": lambda d: received.append(d),
        }
        parser = make_directive_parser(handlers, write_strategy=False)
        bb = Blackboard(data={})
        response = '```json\n{"directives": [{"type": "act", "v": 1}]}\n```'
        parser(response, bb)
        assert len(received) == 1
        assert received[0] == {"type": "act", "v": 1}

    def test_plain_code_fence_stripped(self) -> None:
        """Response wrapped in ``` ... ``` (no language tag) is parsed."""
        handlers: dict[str, DirectiveHandler] = {}
        parser = make_directive_parser(handlers, write_strategy=True)
        bb = Blackboard(data={})
        response = '```\n{"key": "value"}\n```'
        parser(response, bb)
        assert bb.data["strategy"]["key"] == "value"


class TestErrorHandling:
    """Tests for invalid input error handling."""

    def test_invalid_json_raises_decode_error(self) -> None:
        """Invalid JSON raises json.JSONDecodeError."""
        parser = make_directive_parser({})
        bb = Blackboard(data={})
        with pytest.raises(json.JSONDecodeError):
            parser("not valid json {{{", bb)

    def test_non_dict_json_raises_value_error(self) -> None:
        """JSON array (non-dict) raises ValueError."""
        parser = make_directive_parser({})
        bb = Blackboard(data={})
        with pytest.raises(ValueError, match="Expected JSON object"):
            parser("[1, 2, 3]", bb)

    def test_json_string_raises_value_error(self) -> None:
        """JSON string literal raises ValueError."""
        parser = make_directive_parser({})
        bb = Blackboard(data={})
        with pytest.raises(ValueError, match="Expected JSON object"):
            parser('"just a string"', bb)

    def test_json_number_raises_value_error(self) -> None:
        """JSON number raises ValueError."""
        parser = make_directive_parser({})
        bb = Blackboard(data={})
        with pytest.raises(ValueError, match="Expected JSON object"):
            parser("42", bb)
