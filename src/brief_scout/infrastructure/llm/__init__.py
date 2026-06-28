"""LLM infrastructure adapters.

Provides LLM adapter implementations that conform to the LLMPort Protocol.
The FakeLLMAdapter is the primary adapter for development and testing,
providing deterministic, zero-cost responses from JSON fixtures.

Real LLM adapters (for OpenAI, Anthropic, Kimi, etc.) can be added here
in the future, all implementing the same LLMPort interface.
"""

from brief_scout.infrastructure.llm.claude_adapter import ClaudeAdapter
from brief_scout.infrastructure.llm.fake_llm_adapter import FakeLLMAdapter
from brief_scout.infrastructure.llm.json_instruction_injector import (
    JsonInstructionInjector,
)
from brief_scout.infrastructure.llm.kimi_adapter import KimiAdapter
from brief_scout.infrastructure.llm.langchain_base import LangChainBaseAdapter
from brief_scout.infrastructure.llm.openai_adapter import OpenAIAdapter
from brief_scout.infrastructure.llm.response_parser import ResponseParser
from brief_scout.infrastructure.llm.schema_describer import SchemaDescriber

__all__ = [
    "ClaudeAdapter",
    "FakeLLMAdapter",
    "JsonInstructionInjector",
    "KimiAdapter",
    "LangChainBaseAdapter",
    "OpenAIAdapter",
    "ResponseParser",
    "SchemaDescriber",
]
