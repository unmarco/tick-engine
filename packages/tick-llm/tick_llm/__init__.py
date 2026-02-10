"""tick-llm - LLM strategic AI layer for the tick engine."""
from __future__ import annotations

from tick_llm.client import LLMClient, LLMError, MockClient
from tick_llm.components import LLMAgent
from tick_llm.config import LLMConfig
from tick_llm.manager import ContextFn, LLMManager, ParserFn
from tick_llm.parsers import default_json_parser, strip_code_fences
from tick_llm.systems import LLMSystem, make_llm_system

__all__ = [
    "ContextFn",
    "LLMAgent",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LLMManager",
    "LLMSystem",
    "MockClient",
    "ParserFn",
    "default_json_parser",
    "make_llm_system",
    "strip_code_fences",
]
