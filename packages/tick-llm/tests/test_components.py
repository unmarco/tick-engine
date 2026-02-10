"""Tests for LLM components."""
from tick_llm.components import LLMAgent


class TestLLMAgent:
    """Test LLMAgent component."""

    def test_creation_required_fields_only(self):
        """Test creating LLMAgent with only required fields."""
        agent = LLMAgent(
            role="predator",
            personality="cunning",
            context="predator_ctx",
        )
        assert agent.role == "predator"
        assert agent.personality == "cunning"
        assert agent.context == "predator_ctx"
        # Verify all defaults match spec
        assert agent.parser == ""
        assert agent.query_interval == 100
        assert agent.priority == 0
        assert agent.last_query_tick == 0
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert agent.max_retries == 3
        assert agent.cooldown_ticks == 200
        assert agent.cooldown_until == 0

    def test_creation_all_fields_specified(self):
        """Test creating LLMAgent with all fields specified."""
        agent = LLMAgent(
            role="guard",
            personality="aggressive",
            context="guard_ctx",
            parser="custom_parser",
            query_interval=50,
            priority=10,
            last_query_tick=100,
            pending=True,
            consecutive_errors=2,
            max_retries=5,
            cooldown_ticks=300,
            cooldown_until=500,
        )
        assert agent.role == "guard"
        assert agent.personality == "aggressive"
        assert agent.context == "guard_ctx"
        assert agent.parser == "custom_parser"
        assert agent.query_interval == 50
        assert agent.priority == 10
        assert agent.last_query_tick == 100
        assert agent.pending is True
        assert agent.consecutive_errors == 2
        assert agent.max_retries == 5
        assert agent.cooldown_ticks == 300
        assert agent.cooldown_until == 500

    def test_mutability(self):
        """Test that LLMAgent fields can be mutated after creation."""
        agent = LLMAgent(
            role="scout",
            personality="cautious",
            context="scout_ctx",
        )
        # Mutate fields
        agent.last_query_tick = 42
        agent.pending = True
        agent.consecutive_errors = 1
        agent.cooldown_until = 200

        assert agent.last_query_tick == 42
        assert agent.pending is True
        assert agent.consecutive_errors == 1
        assert agent.cooldown_until == 200

    def test_is_dataclass(self):
        """Test that LLMAgent is a proper dataclass."""
        agent = LLMAgent(
            role="test",
            personality="test",
            context="test",
        )
        # Check for dataclass marker
        assert hasattr(agent, "__dataclass_fields__")
        fields = agent.__dataclass_fields__
        assert "role" in fields
        assert "personality" in fields
        assert "context" in fields
        assert "parser" in fields
        assert "query_interval" in fields
        assert "priority" in fields
        assert "last_query_tick" in fields
        assert "pending" in fields
        assert "consecutive_errors" in fields
        assert "max_retries" in fields
        assert "cooldown_ticks" in fields
        assert "cooldown_until" in fields

    def test_default_values_match_spec(self):
        """Test that all default values match the specification exactly."""
        agent = LLMAgent(
            role="test",
            personality="test",
            context="test",
        )
        # Verify defaults as specified in the task
        assert agent.parser == ""
        assert agent.query_interval == 100
        assert agent.priority == 0
        assert agent.last_query_tick == 0
        assert agent.pending is False
        assert agent.consecutive_errors == 0
        assert agent.max_retries == 3
        assert agent.cooldown_ticks == 200
        assert agent.cooldown_until == 0
