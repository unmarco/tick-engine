"""Tests for LLMManager registry."""
from tick import Engine

from tick_llm.client import MockClient
from tick_llm.components import LLMAgent
from tick_llm.config import LLMConfig
from tick_llm.manager import ContextFn, LLMManager, ParserFn


class TestLLMManagerConstructor:
    """Test LLMManager constructor."""

    def test_constructor_no_args(self):
        """Test constructor with no args creates default config."""
        manager = LLMManager()
        # Should have a config (verify it exists)
        # We can't directly access config but we can verify manager was created
        assert manager is not None

    def test_constructor_custom_config(self):
        """Test constructor with custom LLMConfig."""
        config = LLMConfig(
            max_queries_per_tick=5,
            max_queries_per_second=20,
            thread_pool_size=8,
            query_timeout=60.0,
        )
        manager = LLMManager(config=config)
        assert manager is not None


class TestRoleDefinition:
    """Test role definition and lookup."""

    def test_define_role(self):
        """Test define_role stores and retrieves role text."""
        manager = LLMManager()
        role_text = "You are a predator in an arena."
        manager.define_role("predator", role_text)

        result = manager.role("predator")
        assert result == role_text

    def test_role_lookup_miss_returns_none(self):
        """Test role lookup returns None for missing role."""
        manager = LLMManager()
        result = manager.role("nonexistent")
        assert result is None

    def test_define_role_overwrites(self):
        """Test defining same role name twice overwrites."""
        manager = LLMManager()
        manager.define_role("test", "first")
        manager.define_role("test", "second")

        result = manager.role("test")
        assert result == "second"


class TestPersonalityDefinition:
    """Test personality definition and lookup."""

    def test_define_personality(self):
        """Test define_personality stores and retrieves personality text."""
        manager = LLMManager()
        personality_text = "You prefer ambush tactics and patience."
        manager.define_personality("cunning", personality_text)

        result = manager.personality("cunning")
        assert result == personality_text

    def test_personality_lookup_miss_returns_none(self):
        """Test personality lookup returns None for missing personality."""
        manager = LLMManager()
        result = manager.personality("nonexistent")
        assert result is None

    def test_define_personality_overwrites(self):
        """Test defining same personality name twice overwrites."""
        manager = LLMManager()
        manager.define_personality("test", "first")
        manager.define_personality("test", "second")

        result = manager.personality("test")
        assert result == "second"


class TestContextDefinition:
    """Test context template definition and lookup."""

    def test_define_context(self):
        """Test define_context stores and retrieves context function."""
        manager = LLMManager()

        def context_fn(world, eid):
            return "Current situation report"

        manager.define_context("test_ctx", context_fn)

        result = manager.context("test_ctx")
        assert result is context_fn

    def test_context_lookup_miss_returns_none(self):
        """Test context lookup returns None for missing context."""
        manager = LLMManager()
        result = manager.context("nonexistent")
        assert result is None

    def test_define_context_overwrites(self):
        """Test defining same context name twice overwrites."""
        manager = LLMManager()

        def context1(world, eid):
            return "first"

        def context2(world, eid):
            return "second"

        manager.define_context("test", context1)
        manager.define_context("test", context2)

        result = manager.context("test")
        assert result is context2


class TestParserDefinition:
    """Test parser definition and lookup."""

    def test_define_parser(self):
        """Test define_parser stores and retrieves parser function."""
        manager = LLMManager()

        def parser_fn(response, blackboard):
            pass

        manager.define_parser("test_parser", parser_fn)

        result = manager.parser("test_parser")
        assert result is parser_fn

    def test_parser_lookup_miss_returns_none(self):
        """Test parser lookup returns None for missing parser."""
        manager = LLMManager()
        result = manager.parser("nonexistent")
        assert result is None

    def test_define_parser_overwrites(self):
        """Test defining same parser name twice overwrites."""
        manager = LLMManager()

        def parser1(response, blackboard):
            pass

        def parser2(response, blackboard):
            pass

        manager.define_parser("test", parser1)
        manager.define_parser("test", parser2)

        result = manager.parser("test")
        assert result is parser2


class TestClientRegistration:
    """Test client registration."""

    def test_register_client(self):
        """Test register_client stores client."""
        manager = LLMManager()
        client = MockClient(responses={})

        manager.register_client(client)

        result = manager.client
        assert result is client

    def test_client_property_returns_none_before_registration(self):
        """Test client property returns None before registration."""
        manager = LLMManager()
        assert manager.client is None


class TestCallbackRegistration:
    """Test callback registration."""

    def test_on_query_callback_registration(self):
        """Test on_query callback registration stores callbacks."""
        manager = LLMManager()
        calls = []

        def callback(eid, prompt_size, tick):
            calls.append(("query", eid, prompt_size, tick))

        manager.on_query(callback)
        # Can't directly verify storage, but verify no error

    def test_on_response_callback_registration(self):
        """Test on_response callback registration."""
        manager = LLMManager()
        calls = []

        def callback(eid, latency, response_size, tick):
            calls.append(("response", eid, latency, response_size, tick))

        manager.on_response(callback)
        # Can't directly verify storage, but verify no error

    def test_on_error_callback_registration(self):
        """Test on_error callback registration."""
        manager = LLMManager()
        calls = []

        def callback(eid, error_type, error_msg, tick):
            calls.append(("error", eid, error_type, error_msg, tick))

        manager.on_error(callback)
        # Can't directly verify storage, but verify no error


class TestAssemblePrompt:
    """Test assemble_prompt method."""

    def test_assemble_prompt_with_all_definitions(self):
        """Test assemble_prompt with all definitions present."""
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()

        manager = LLMManager()
        manager.define_role("test_role", "Role text")
        manager.define_personality("test_personality", "Personality text")

        def context_fn(world, eid):
            return "Context message"

        manager.define_context("test_context", context_fn)

        agent = LLMAgent(
            role="test_role",
            personality="test_personality",
            context="test_context",
        )

        result = manager.assemble_prompt(engine.world, eid, agent)

        assert result is not None
        system_prompt, user_message = result
        assert system_prompt == "Role text\n\nPersonality text"
        assert user_message == "Context message"

    def test_assemble_prompt_missing_role_returns_none(self):
        """Test assemble_prompt with missing role returns None."""
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()

        manager = LLMManager()
        manager.define_personality("test_personality", "Personality text")

        def context_fn(world, eid):
            return "Context message"

        manager.define_context("test_context", context_fn)

        agent = LLMAgent(
            role="missing_role",
            personality="test_personality",
            context="test_context",
        )

        result = manager.assemble_prompt(engine.world, eid, agent)
        assert result is None

    def test_assemble_prompt_missing_personality_returns_none(self):
        """Test assemble_prompt with missing personality returns None."""
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()

        manager = LLMManager()
        manager.define_role("test_role", "Role text")

        def context_fn(world, eid):
            return "Context message"

        manager.define_context("test_context", context_fn)

        agent = LLMAgent(
            role="test_role",
            personality="missing_personality",
            context="test_context",
        )

        result = manager.assemble_prompt(engine.world, eid, agent)
        assert result is None

    def test_assemble_prompt_missing_context_returns_none(self):
        """Test assemble_prompt with missing context returns None."""
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()

        manager = LLMManager()
        manager.define_role("test_role", "Role text")
        manager.define_personality("test_personality", "Personality text")

        agent = LLMAgent(
            role="test_role",
            personality="test_personality",
            context="missing_context",
        )

        result = manager.assemble_prompt(engine.world, eid, agent)
        assert result is None

    def test_assemble_prompt_context_receives_world_and_eid(self):
        """Test assemble_prompt passes world and eid to context function."""
        engine = Engine(tps=20, seed=42)
        eid = engine.world.spawn()

        manager = LLMManager()
        manager.define_role("test_role", "Role text")
        manager.define_personality("test_personality", "Personality text")

        received_args = []

        def context_fn(world, entity_id):
            received_args.append((world, entity_id))
            return "Context"

        manager.define_context("test_context", context_fn)

        agent = LLMAgent(
            role="test_role",
            personality="test_personality",
            context="test_context",
        )

        manager.assemble_prompt(engine.world, eid, agent)

        assert len(received_args) == 1
        assert received_args[0][0] is engine.world
        assert received_args[0][1] == eid
