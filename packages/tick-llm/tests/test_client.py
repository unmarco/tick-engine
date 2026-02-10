"""Tests for LLM client protocol and mock client."""
import time

import pytest

from tick_llm.client import LLMClient, LLMError, MockClient


class TestLLMClientProtocol:
    """Test LLMClient protocol conformance."""

    def test_mock_client_conforms_to_protocol(self):
        """Test MockClient conforms to LLMClient protocol."""
        client = MockClient(responses={})
        # Protocol is @runtime_checkable, so isinstance should work
        assert isinstance(client, LLMClient)


class TestMockClientResponses:
    """Test MockClient response handling."""

    def test_mock_client_with_dict_responses(self):
        """Test MockClient returns mapped response for matching key."""
        responses = {
            ("system1", "user1"): "response1",
            ("system2", "user2"): "response2",
        }
        client = MockClient(responses=responses)

        result = client.query("system1", "user1")
        assert result == "response1"

        result = client.query("system2", "user2")
        assert result == "response2"

    def test_mock_client_dict_missing_key_returns_empty_json(self):
        """Test MockClient returns '{}' for missing key in dict."""
        responses = {
            ("system1", "user1"): "response1",
        }
        client = MockClient(responses=responses)

        result = client.query("missing_system", "missing_user")
        assert result == "{}"

    def test_mock_client_with_callable_responses(self):
        """Test MockClient with callable responses."""

        def dynamic_response(system_prompt: str, user_message: str) -> str:
            return f"System: {system_prompt}, User: {user_message}"

        client = MockClient(responses=dynamic_response)

        result = client.query("sys", "usr")
        assert result == "System: sys, User: usr"


class TestMockClientLatency:
    """Test MockClient latency simulation."""

    def test_mock_client_with_latency(self):
        """Test MockClient with latency > 0 simulates delay."""
        responses = {("sys", "usr"): "response"}
        client = MockClient(responses=responses, latency=0.1)

        start = time.monotonic()
        result = client.query("sys", "usr")
        duration = time.monotonic() - start

        assert result == "response"
        # Should take at least 0.1 seconds
        assert duration >= 0.1


class TestMockClientErrorRate:
    """Test MockClient error simulation."""

    def test_mock_client_error_rate_always_raises(self):
        """Test MockClient with error_rate=1.0 always raises."""
        responses = {("sys", "usr"): "response"}
        client = MockClient(responses=responses, error_rate=1.0)

        with pytest.raises(LLMError):
            client.query("sys", "usr")

    def test_mock_client_error_rate_never_raises(self):
        """Test MockClient with error_rate=0.0 never raises."""
        responses = {("sys", "usr"): "response"}
        client = MockClient(responses=responses, error_rate=0.0)

        # Should not raise
        result = client.query("sys", "usr")
        assert result == "response"


class TestLLMError:
    """Test LLMError exception."""

    def test_llm_error_default_exception(self):
        """Test MockClient default error is LLMError."""
        responses = {("sys", "usr"): "response"}
        client = MockClient(responses=responses, error_rate=1.0)

        with pytest.raises(LLMError):
            client.query("sys", "usr")

    def test_llm_error_is_exception_subclass(self):
        """Test LLMError is an Exception subclass."""
        assert issubclass(LLMError, Exception)
