"""Tests for LLM response parsers."""
import json

import pytest

from tick_ai.components import Blackboard
from tick_llm.parsers import default_json_parser, strip_code_fences


class TestStripCodeFences:
    """Test strip_code_fences utility."""

    def test_strip_json_code_fences(self):
        """Test stripping ```json ... ``` wrapping."""
        input_text = "```json\n{\"key\": \"value\"}\n```"
        result = strip_code_fences(input_text)
        assert result == "{\"key\": \"value\"}"

    def test_strip_generic_code_fences(self):
        """Test stripping ``` ... ``` wrapping without language tag."""
        input_text = "```\n{\"key\": \"value\"}\n```"
        result = strip_code_fences(input_text)
        assert result == "{\"key\": \"value\"}"

    def test_strip_code_fences_no_fences(self):
        """Test strip_code_fences returns input unchanged when no fences."""
        input_text = "{\"key\": \"value\"}"
        result = strip_code_fences(input_text)
        assert result == "{\"key\": \"value\"}"

    def test_strip_code_fences_just_backticks(self):
        """Test strip_code_fences with edge case of just backticks."""
        input_text = "```"
        result = strip_code_fences(input_text)
        # Should return stripped or original - spec doesn't detail edge case
        # Just verify it doesn't crash
        assert isinstance(result, str)


class TestDefaultJsonParser:
    """Test default_json_parser."""

    def test_default_json_parser_valid_json_dict(self):
        """Test default_json_parser with valid JSON dict merges into strategy."""
        blackboard = Blackboard()
        response = '{"goal": "hunt", "stance": "aggressive"}'

        default_json_parser(response, blackboard)

        assert "strategy" in blackboard.data
        assert blackboard.data["strategy"]["goal"] == "hunt"
        assert blackboard.data["strategy"]["stance"] == "aggressive"

    def test_default_json_parser_preserves_existing_strategy(self):
        """Test default_json_parser preserves existing strategy keys (shallow merge)."""
        blackboard = Blackboard()
        blackboard.data["strategy"] = {
            "existing_key": "existing_value",
            "goal": "old_goal",
        }
        response = '{"goal": "new_goal", "new_key": "new_value"}'

        default_json_parser(response, blackboard)

        # Shallow merge should preserve existing_key, update goal, add new_key
        assert blackboard.data["strategy"]["existing_key"] == "existing_value"
        assert blackboard.data["strategy"]["goal"] == "new_goal"
        assert blackboard.data["strategy"]["new_key"] == "new_value"

    def test_default_json_parser_creates_strategy_key(self):
        """Test default_json_parser creates strategy key if not present."""
        blackboard = Blackboard()
        # No strategy key initially
        assert "strategy" not in blackboard.data

        response = '{"goal": "patrol"}'
        default_json_parser(response, blackboard)

        assert "strategy" in blackboard.data
        assert blackboard.data["strategy"]["goal"] == "patrol"

    def test_default_json_parser_invalid_json_raises(self):
        """Test default_json_parser with invalid JSON raises exception."""
        blackboard = Blackboard()
        response = '{"invalid": json syntax}'

        # Should raise json.JSONDecodeError or ValueError
        with pytest.raises((json.JSONDecodeError, ValueError)):
            default_json_parser(response, blackboard)

    def test_default_json_parser_non_dict_json_raises(self):
        """Test default_json_parser with non-dict JSON raises ValueError."""
        blackboard = Blackboard()
        # Valid JSON but not a dict
        response = '["item1", "item2"]'

        with pytest.raises(ValueError):
            default_json_parser(response, blackboard)

    def test_default_json_parser_strips_code_fences(self):
        """Test default_json_parser strips code fences before parsing."""
        blackboard = Blackboard()
        response = '```json\n{"goal": "ambush"}\n```'

        default_json_parser(response, blackboard)

        assert "strategy" in blackboard.data
        assert blackboard.data["strategy"]["goal"] == "ambush"

    def test_default_json_parser_with_nested_dict(self):
        """Test default_json_parser with nested dict values."""
        blackboard = Blackboard()
        response = '{"goal": "hunt", "plan": {"phase": 1, "target": 7}}'

        default_json_parser(response, blackboard)

        assert blackboard.data["strategy"]["goal"] == "hunt"
        assert blackboard.data["strategy"]["plan"]["phase"] == 1
        assert blackboard.data["strategy"]["plan"]["target"] == 7

    def test_default_json_parser_empty_dict(self):
        """Test default_json_parser with empty dict."""
        blackboard = Blackboard()
        response = '{}'

        default_json_parser(response, blackboard)

        # Should create strategy as empty dict
        assert "strategy" in blackboard.data
        assert blackboard.data["strategy"] == {}

    def test_default_json_parser_other_blackboard_keys_preserved(self):
        """Test default_json_parser does not affect other blackboard keys."""
        blackboard = Blackboard()
        blackboard.data["hp"] = 100
        blackboard.data["position"] = (5, 5)

        response = '{"goal": "rest"}'
        default_json_parser(response, blackboard)

        # Other keys should remain unchanged
        assert blackboard.data["hp"] == 100
        assert blackboard.data["position"] == (5, 5)
        assert blackboard.data["strategy"]["goal"] == "rest"
