"""Unit tests for the ClaudeAdapter.

Tests cover:
- complete() returns LLMResponse with correct provider
- Claude-specific message format (system as separate param, not in messages)
- complete_structured() parses JSON into Pydantic model
- Timeout raises LLMCallError
- API error handling
- _build_messages excludes system role
- _inject_json_instructions
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.infrastructure.llm.claude_adapter import ClaudeAdapter

# ---------------------------------------------------------------------------
# Pydantic schemas for structured-output tests
# ---------------------------------------------------------------------------


class BrandInfo(BaseModel):
    """Test schema for brand extraction."""

    brand_name: str
    industry: str


class CompetitorList(BaseModel):
    """Test schema for competitor lists."""

    competitors: list[str]
    count: int


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> ClaudeAdapter:
    """Return a ClaudeAdapter with a dummy API key."""
    return ClaudeAdapter(api_key="test-key")


@pytest.fixture
def mock_claude_client() -> MagicMock:
    """Return a mock Anthropic client with a realistic response."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text='{"brand_name": "Nike", "industry": "sportswear"}')],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=30, output_tokens=20),
        )
    )
    return mock


@pytest.fixture
def sample_prompt() -> Prompt:
    """Return a standard Prompt for testing."""
    return Prompt(
        system="You are a helpful assistant.",
        user="What is the capital of France?",
        context=[{"role": "user", "content": "Previous message"}],
    )


# ---------------------------------------------------------------------------
# 1. complete() core behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_returns_llm_response(
    adapter: ClaudeAdapter,
    mock_claude_client: MagicMock,
    sample_prompt: Prompt,
) -> None:
    """complete() must return an LLMResponse with correct provider."""
    with patch.object(adapter, "_get_client", return_value=mock_claude_client):
        result = await adapter.complete(sample_prompt)

    assert isinstance(result, LLMResponse)
    assert result.provider == "claude"
    assert result.model_used == "claude-3-haiku-20240307"
    assert result.tokens_used == 50  # 30 + 20
    assert result.finish_reason == "end_turn"
    assert result.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_complete_content_extraction(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """complete() must extract content from response.content[0].text."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="Paris is the capital of France.")],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=15, output_tokens=10),
        )
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete(sample_prompt)

    assert result.content == "Paris is the capital of France."
    assert result.tokens_used == 25


@pytest.mark.asyncio
async def test_complete_no_usage_data(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """complete() must handle responses without usage data gracefully."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="Hello")],
            model="claude-3-haiku-20240307",
            stop_reason="stop",
            stop_sequence=None,
            # No usage attribute
            spec=["content", "model", "stop_reason", "stop_sequence"],
        )
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete(sample_prompt)

    assert result.tokens_used == 0
    assert result.content == "Hello"


@pytest.mark.asyncio
async def test_complete_empty_content(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """complete() must handle empty content list."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=5, output_tokens=0),
        )
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete(sample_prompt)

    assert result.content == ""
    assert result.tokens_used == 5


@pytest.mark.asyncio
async def test_complete_model_override_via_config(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """complete() must respect model override in config."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="OK")],
            model="claude-3-5-sonnet-20241022",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=10, output_tokens=5),
        )
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete(
            sample_prompt, config={"model": "claude-3-5-sonnet-20241022"}
        )

    assert result.model_used == "claude-3-5-sonnet-20241022"


# ---------------------------------------------------------------------------
# 2. Claude-specific message format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_sent_as_separate_parameter(
    adapter: ClaudeAdapter,
    mock_claude_client: MagicMock,
) -> None:
    """System prompt must be sent as a top-level ``system`` kwarg, not in messages."""
    prompt = Prompt(
        system="You are an expert analyst.",
        user="Analyze this brand.",
        context=[],
    )

    with patch.object(adapter, "_get_client", return_value=mock_claude_client):
        await adapter.complete(prompt)

    call_kwargs = mock_claude_client.messages.create.call_args.kwargs
    assert "system" in call_kwargs
    assert call_kwargs["system"] == "You are an expert analyst."
    # System should NOT appear in messages
    for msg in call_kwargs["messages"]:
        assert msg.get("role") != "system"


@pytest.mark.asyncio
async def test_no_system_parameter_when_system_empty(
    adapter: ClaudeAdapter,
    mock_claude_client: MagicMock,
) -> None:
    """When system prompt is empty, no ``system`` key should be sent."""
    prompt = Prompt(
        system="",
        user="Hello",
        context=[],
    )

    with patch.object(adapter, "_get_client", return_value=mock_claude_client):
        await adapter.complete(prompt)

    call_kwargs = mock_claude_client.messages.create.call_args.kwargs
    assert "system" not in call_kwargs


# ---------------------------------------------------------------------------
# 3. complete_structured()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_structured_parses_json(
    adapter: ClaudeAdapter,
) -> None:
    """complete_structured() must parse JSON response into Pydantic model."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text='{"brand_name": "Nike", "industry": "sportswear"}')],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=30, output_tokens=15),
        )
    )

    prompt = Prompt(
        system="Extract brand info.",
        user="Tell me about Nike.",
        context=[],
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete_structured(prompt, BrandInfo)

    assert isinstance(result, BrandInfo)
    assert result.brand_name == "Nike"
    assert result.industry == "sportswear"


@pytest.mark.asyncio
async def test_complete_structured_strips_markdown_fences(
    adapter: ClaudeAdapter,
) -> None:
    """complete_structured() must strip ```json ... ``` markdown wrappers."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[
                MagicMock(text='```json\n{"brand_name": "Adidas", "industry": "sportswear"}\n```')
            ],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=25, output_tokens=15),
        )
    )

    prompt = Prompt(
        system="Extract brand info.",
        user="Tell me about Adidas.",
        context=[],
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete_structured(prompt, BrandInfo)

    assert result.brand_name == "Adidas"
    assert result.industry == "sportswear"


@pytest.mark.asyncio
async def test_complete_structured_strips_generic_code_fences(
    adapter: ClaudeAdapter,
) -> None:
    """complete_structured() must strip ``` ... ``` markdown wrappers without json label."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text='```\n{"brand_name": "Puma", "industry": "sportswear"}\n```')],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=25, output_tokens=15),
        )
    )

    prompt = Prompt(
        system="Extract brand info.",
        user="Tell me about Puma.",
        context=[],
    )

    with patch.object(adapter, "_get_client", return_value=mock):
        result = await adapter.complete_structured(prompt, BrandInfo)

    assert result.brand_name == "Puma"
    assert result.industry == "sportswear"


@pytest.mark.asyncio
async def test_complete_structured_raises_on_bad_json(
    adapter: ClaudeAdapter,
) -> None:
    """complete_structured() must raise LLMCallError when JSON is unparseable."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="This is not JSON at all")],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=20, output_tokens=10),
        )
    )

    prompt = Prompt(
        system="Extract brand info.",
        user="Tell me about a brand.",
        context=[],
    )

    with (
        patch.object(adapter, "_get_client", return_value=mock),
        pytest.raises(LLMCallError) as exc_info,
    ):
        await adapter.complete_structured(prompt, BrandInfo)

    assert "Failed to parse structured output" in str(exc_info.value)
    assert exc_info.value.provider == "claude"
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_complete_structured_raises_on_validation_error(
    adapter: ClaudeAdapter,
) -> None:
    """complete_structured() must raise LLMCallError when JSON doesn't match schema."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text='{"brand_name": "Nike"}')],  # missing "industry"
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=MagicMock(input_tokens=20, output_tokens=10),
        )
    )

    # BrandInfo requires both brand_name and industry
    prompt = Prompt(
        system="Extract brand info.",
        user="Tell me about Nike.",
        context=[],
    )

    with (
        patch.object(adapter, "_get_client", return_value=mock),
        pytest.raises(LLMCallError) as exc_info,
    ):
        await adapter.complete_structured(prompt, BrandInfo)

    assert "Failed to parse structured output" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Timeout handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_timeout_raises_llm_call_error(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """A timeout must result in an LLMCallError with retryable=True."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(side_effect=asyncio.TimeoutError)

    with (
        patch.object(adapter, "_get_client", return_value=mock),
        pytest.raises(LLMCallError) as exc_info,
    ):
        await adapter.complete(sample_prompt)

    assert "timed out" in str(exc_info.value).lower()
    assert exc_info.value.provider == "claude"
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_complete_custom_timeout_via_config(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """Timeout value from config must be passed to asyncio.wait_for."""
    mock = MagicMock()
    mock.messages = MagicMock()

    async def slow_create(**_kwargs: Any) -> MagicMock:
        await asyncio.sleep(999)  # Will be cancelled by timeout
        return MagicMock()

    mock.messages.create = AsyncMock(side_effect=slow_create)

    with patch.object(adapter, "_get_client", return_value=mock), pytest.raises(LLMCallError):
        await adapter.complete(sample_prompt, config={"timeout_seconds": 0.01})


# ---------------------------------------------------------------------------
# 5. API error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_api_error_raises_llm_call_error(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """Generic API errors must be wrapped in LLMCallError."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(side_effect=Exception("auth error"))

    with (
        patch.object(adapter, "_get_client", return_value=mock),
        pytest.raises(LLMCallError) as exc_info,
    ):
        await adapter.complete(sample_prompt)

    assert "auth error" in str(exc_info.value)
    assert exc_info.value.provider == "claude"


@pytest.mark.asyncio
async def test_rate_limit_error_is_retryable(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """Rate limit errors must be marked as retryable."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(side_effect=Exception("Rate limit exceeded, retry after 30s"))

    with (
        patch.object(adapter, "_get_client", return_value=mock),
        pytest.raises(LLMCallError) as exc_info,
    ):
        await adapter.complete(sample_prompt)

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_auth_error_is_not_retryable(
    adapter: ClaudeAdapter,
    sample_prompt: Prompt,
) -> None:
    """Auth errors must be marked as non-retryable."""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(side_effect=Exception("invalid auth token"))

    with (
        patch.object(adapter, "_get_client", return_value=mock),
        pytest.raises(LLMCallError) as exc_info,
    ):
        await adapter.complete(sample_prompt)

    assert exc_info.value.retryable is False


# ---------------------------------------------------------------------------
# 6. _build_messages()
# ---------------------------------------------------------------------------


def test_build_messages_excludes_system_role(adapter: ClaudeAdapter) -> None:
    """_build_messages must never include a system role entry."""
    prompt = Prompt(
        system="You are an expert.",
        user="What is AI?",
        context=[
            {"role": "system", "content": "System context"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ],
    )

    messages = adapter._build_messages(prompt)

    roles = [msg["role"] for msg in messages]
    assert "system" not in roles
    assert roles == ["user", "assistant", "user"]


def test_build_messages_includes_context(adapter: ClaudeAdapter) -> None:
    """_build_messages must include context entries in order."""
    prompt = Prompt(
        system="",
        user="Final question",
        context=[
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Second"},
        ],
    )

    messages = adapter._build_messages(prompt)

    assert len(messages) == 3
    assert messages[0] == {"role": "user", "content": "First"}
    assert messages[1] == {"role": "assistant", "content": "Second"}
    assert messages[2] == {"role": "user", "content": "Final question"}


def test_build_messages_empty_context(adapter: ClaudeAdapter) -> None:
    """_build_messages with empty context should only include the user message."""
    prompt = Prompt(
        system="",
        user="Hello",
        context=[],
    )

    messages = adapter._build_messages(prompt)

    assert len(messages) == 1
    assert messages[0] == {"role": "user", "content": "Hello"}


def test_build_messages_skips_only_system_context(adapter: ClaudeAdapter) -> None:
    """When all context entries are system role, only user message remains."""
    prompt = Prompt(
        system="System prompt",
        user="User question",
        context=[
            {"role": "system", "content": "Sys 1"},
            {"role": "system", "content": "Sys 2"},
        ],
    )

    messages = adapter._build_messages(prompt)

    assert len(messages) == 1
    assert messages[0] == {"role": "user", "content": "User question"}


# ---------------------------------------------------------------------------
# 7. _inject_json_instructions()
# ---------------------------------------------------------------------------


def test_inject_json_instructions_adds_schema_hint(adapter: ClaudeAdapter) -> None:
    """_inject_json_instructions must append JSON instructions to system prompt."""
    prompt = Prompt(
        system="Extract info.",
        user="Tell me about Nike.",
        context=[],
    )

    result = adapter._inject_json_instructions(prompt, BrandInfo)

    assert "You must respond with ONLY a valid JSON" in result.system
    assert "brand_name" in result.system
    assert "industry" in result.system
    assert result.user == prompt.user  # Unchanged
    assert result.context == prompt.context  # Unchanged


def test_inject_json_instructions_preserves_original_system(adapter: ClaudeAdapter) -> None:
    """Original system prompt content must be preserved before the JSON instructions."""
    prompt = Prompt(
        system="You are a brand analyst. Be concise.",
        user="Analyze Adidas.",
        context=[],
    )

    result = adapter._inject_json_instructions(prompt, BrandInfo)

    assert result.system.startswith("You are a brand analyst. Be concise.")
    assert "JSON" in result.system


def test_inject_json_instructions_describes_schema() -> None:
    """The schema description should list all fields with their types."""
    desc = ClaudeAdapter._describe_schema(BrandInfo)

    assert "brand_name" in desc
    assert "industry" in desc


def test_inject_json_instructions_list_schema() -> None:
    """_describe_schema should handle list types gracefully."""
    desc = ClaudeAdapter._describe_schema(CompetitorList)

    assert "competitors" in desc
    assert "count" in desc


# ---------------------------------------------------------------------------
# 8. Provider name & config
# ---------------------------------------------------------------------------


def test_provider_name(adapter: ClaudeAdapter) -> None:
    """provider_name must return 'claude'."""
    assert adapter.provider_name == "claude"


def test_merge_config_with_override(adapter: ClaudeAdapter) -> None:
    """_merge_config must apply overrides on top of defaults."""
    merged = adapter._merge_config({"temperature": 0.9, "max_tokens": 500})

    assert merged["temperature"] == 0.9
    assert merged["max_tokens"] == 500
    assert merged["model"] == "claude-3-haiku-20240307"  # Default preserved


def test_merge_config_none(adapter: ClaudeAdapter) -> None:
    """_merge_config with None must return only defaults."""
    merged = adapter._merge_config(None)

    assert merged["temperature"] == 0.3
    assert merged["max_tokens"] == 2000
    assert merged["model"] == "claude-3-haiku-20240307"
    assert merged["timeout_seconds"] == 60.0


# ---------------------------------------------------------------------------
# 9. Lazy client initialisation
# ---------------------------------------------------------------------------


def test_lazy_client_init(adapter: ClaudeAdapter) -> None:
    """The Anthropic client must not be created until first use."""
    assert adapter._client is None


def test_get_client_creates_instance(adapter: ClaudeAdapter) -> None:
    """_get_client must create and cache the client."""
    mock_instance = MagicMock()
    mock_async_class = MagicMock(return_value=mock_instance)
    fake_module = MagicMock(AsyncAnthropic=mock_async_class)

    with patch.dict("sys.modules", {"anthropic": fake_module}):
        client = adapter._get_client()

        mock_async_class.assert_called_once_with(api_key="test-key")
        assert client is mock_instance
        assert adapter._client is mock_instance


def test_get_client_with_base_url() -> None:
    """_get_client must pass base_url when provided."""
    adp = ClaudeAdapter(api_key="key", base_url="https://custom.example.com")

    mock_instance = MagicMock()
    mock_async_class = MagicMock(return_value=mock_instance)
    fake_module = MagicMock(AsyncAnthropic=mock_async_class)

    with patch.dict("sys.modules", {"anthropic": fake_module}):
        adp._get_client()

        mock_async_class.assert_called_once_with(
            api_key="key",
            base_url="https://custom.example.com",
        )


def test_get_client_uses_env_var() -> None:
    """When no api_key is passed, ANTHROPIC_API_KEY env var should be used."""
    mock_instance = MagicMock()
    mock_async_class = MagicMock(return_value=mock_instance)
    fake_module = MagicMock(AsyncAnthropic=mock_async_class)

    with (
        patch.dict("sys.modules", {"anthropic": fake_module}),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}),
    ):
        adp = ClaudeAdapter()
        adp._get_client()

        mock_async_class.assert_called_once_with(api_key="env-key")


# ---------------------------------------------------------------------------
# 10. Telemetry passthrough
# ---------------------------------------------------------------------------


def test_telemetry_attribute_stored() -> None:
    """Telemetry object should be stored on the adapter."""
    telemetry = MagicMock()
    adp = ClaudeAdapter(api_key="k", telemetry=telemetry)
    assert adp._telemetry is telemetry
