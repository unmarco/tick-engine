"""LLMManager — central registry for roles, personalities, contexts, and parsers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_ai.components import Blackboard

from tick_llm.client import LLMClient
from tick_llm.components import LLMAgent
from tick_llm.config import LLMConfig

if TYPE_CHECKING:
    from tick import World

# Type aliases for context template and parser callables.
ContextFn = Callable[["World", int], str]
ParserFn = Callable[[str, Blackboard], None]


class LLMManager:
    """Central registry for LLM prompt components and client.

    Follows the same registry pattern as AIManager: define by name, look up
    by name, assemble prompts from named components.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config: LLMConfig = config if config is not None else LLMConfig()

        # Registries
        self._roles: dict[str, str] = {}
        self._personalities: dict[str, str] = {}
        self._contexts: dict[str, ContextFn] = {}
        self._parsers: dict[str, ParserFn] = {}

        # Client
        self._client: LLMClient | None = None

        # Observable callbacks
        self._on_query: list[Callable[[int, int, int], None]] = []
        self._on_response: list[Callable[[int, float, int, int], None]] = []
        self._on_error: list[Callable[[int, str, str, int], None]] = []

    # --- Definition methods ---

    def define_role(self, name: str, text: str) -> None:
        """Register a static role prompt fragment."""
        self._roles[name] = text

    def define_personality(self, name: str, text: str) -> None:
        """Register a static personality prompt fragment."""
        self._personalities[name] = text

    def define_context(self, name: str, fn: ContextFn) -> None:
        """Register a context template callable: (World, eid) -> str."""
        self._contexts[name] = fn

    def define_parser(self, name: str, fn: ParserFn) -> None:
        """Register a response parser callable: (str, Blackboard) -> None."""
        self._parsers[name] = fn

    def register_client(self, client: LLMClient) -> None:
        """Set the LLM client implementation."""
        self._client = client

    # --- Lookup methods ---

    def role(self, name: str) -> str | None:
        """Look up a role definition by name."""
        return self._roles.get(name)

    def personality(self, name: str) -> str | None:
        """Look up a personality definition by name."""
        return self._personalities.get(name)

    def context(self, name: str) -> ContextFn | None:
        """Look up a context template by name."""
        return self._contexts.get(name)

    def parser(self, name: str) -> ParserFn | None:
        """Look up a parser by name."""
        return self._parsers.get(name)

    # --- Client property ---

    @property
    def client(self) -> LLMClient | None:
        """The registered LLM client, or None if not yet registered."""
        return self._client

    # --- Callback registration ---

    def on_query(self, cb: Callable[[int, int, int], None]) -> None:
        """Register callback fired on query dispatch.

        Signature: (eid, prompt_size_chars, tick_number) -> None.
        """
        self._on_query.append(cb)

    def on_response(self, cb: Callable[[int, float, int, int], None]) -> None:
        """Register callback fired on response receipt.

        Signature: (eid, latency_seconds, response_size_chars, tick_number) -> None.
        """
        self._on_response.append(cb)

    def on_error(self, cb: Callable[[int, str, str, int], None]) -> None:
        """Register callback fired on any failure.

        Signature: (eid, error_type, error_message, tick_number) -> None.
        """
        self._on_error.append(cb)

    # --- Prompt assembly ---

    def assemble_prompt(
        self, world: World, eid: int, agent: LLMAgent
    ) -> tuple[str, str] | None:
        """Assemble a prompt from registered components.

        Returns (system_prompt, user_message) or None if any referenced
        definition (role, personality, context) is missing.
        """
        role_text = self._roles.get(agent.role)
        if role_text is None:
            return None

        personality_text = self._personalities.get(agent.personality)
        if personality_text is None:
            return None

        context_fn = self._contexts.get(agent.context)
        if context_fn is None:
            return None

        system_prompt = role_text + "\n\n" + personality_text
        user_message = context_fn(world, eid)
        return (system_prompt, user_message)
