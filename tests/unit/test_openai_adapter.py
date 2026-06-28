"""Comprehensive unit tests for OpenAIAdapter.

Tests the OpenAI LLM adapter using mocked AsyncOpenAI client.
Target: 90% coverage. All API calls are mocked — no real network requests.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import ChatMessage, LLMResponse, Prompt
from brief_scout.infrastructure.llm.openai_adapter import OpenAIAdapter

# ---------------------------------------------------------------------------
# Pydantic schema for structured output tests
# ---------------------------------------------------------------------------


class _TestBrandOutput(BaseModel):
    """Test schema for structured output parsing."""

    brand_name: str
    positioning: str
    key_messages: list[str]


class _TestSimpleOutput(BaseModel):
    """Minimal test schema."""

    answer: str
    score: int


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> OpenAIAdapter:
    """Provide an OpenAIAdapter with a dummy API key."""
    return OpenAIAdapter(api_key="test-key-sk-1234")


@pytest.fixture
def mock_openai_response() -> MagicMock:
    """Provide a mock OpenAI chat completions response."""
    return MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"brand_name": "Nike", "positioning": "Just Do It", "key_messages": ["authenticity", "performance"]}'
                ),
                finish_reason="stop",
            )
        ],
        model="gpt-4o-mini",
        usage=MagicMock(
            total_tokens=50,
            prompt_tokens=30,
            completion_tokens=20,
        ),
    )


@pytest.fixture
def mock_openai_client(mock_openai_response: MagicMock) -> AsyncMock:
    """Provide a fully mocked AsyncOpenAI client."""
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=mock_openai_response)
    return mock


@pytest.fixture
def prompt() -> Prompt:
    """Provide a standard Prompt instance."""
    return Prompt(
        system="You are a helpful assistant.",
        user="Tell me about Nike.",
        context=[{"role": "assistant", "content": "Previous context"}],
    )


# ============================================================================
# Tests
# ============================================================================


class TestOpenAIAdapterInit:
    """Tests for OpenAIAdapter construction and configuration."""

    def test_should_use_provided_api_key(self) -> None:
        """Adapter should use the API key passed to the constructor."""
        adapter = OpenAIAdapter(api_key="explicit-key")
        assert adapter._api_key == "explicit-key"

    def test_should_use_default_model(self) -> None:
        """Adapter should default to gpt-4o-mini."""
        adapter = OpenAIAdapter(api_key="test-key")
        assert adapter._model == "gpt-4o-mini"

    def test_should_accept_custom_model(self) -> None:
        """Adapter should accept a custom model identifier."""
        adapter = OpenAIAdapter(api_key="test-key", model="gpt-4o")
        assert adapter._model == "gpt-4o"

    def test_should_store_all_config_params(self) -> None:
        """Adapter should store all constructor parameters."""
        adapter = OpenAIAdapter(
            api_key="k",
            model="m",
            base_url="https://proxy.example.com",
            temperature=0.7,
            max_tokens=1000,
            timeout_seconds=30.0,
        )
        assert adapter._base_url == "https://proxy.example.com"
        assert adapter._temperature == 0.7
        assert adapter._max_tokens == 1000
        assert adapter._timeout == 30.0

    def test_should_lazy_init_client(self, adapter: OpenAIAdapter) -> None:
        """Client should be None until _get_client is called."""
        assert adapter._client is None

    @patch("openai.AsyncOpenAI")
    def test_should_create_client_with_api_key(self, mock_client_cls: MagicMock) -> None:
        """_get_client should create AsyncOpenAI with the API key."""
        adapter = OpenAIAdapter(api_key="my-key")
        adapter._get_client()
        mock_client_cls.assert_called_once_with(api_key="my-key")

    @patch("openai.AsyncOpenAI")
    def test_should_create_client_with_base_url(self, mock_client_cls: MagicMock) -> None:
        """_get_client should pass base_url when configured."""
        adapter = OpenAIAdapter(api_key="k", base_url="https://proxy.example.com")
        adapter._get_client()
        mock_client_cls.assert_called_once_with(
            api_key="k",
            base_url="https://proxy.example.com",
        )

    @patch("openai.AsyncOpenAI")
    def test_should_reuse_client_on_subsequent_calls(
        self,
        mock_cls: MagicMock,
        adapter: OpenAIAdapter,
    ) -> None:
        """_get_client should return the same client instance."""
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        c1 = adapter._get_client()
        c2 = adapter._get_client()
        assert c1 is c2
        mock_cls.assert_called_once()


class TestProviderName:
    """Tests for the provider_name property."""

    def test_should_return_openai(self, adapter: OpenAIAdapter) -> None:
        """provider_name should return 'openai'."""
        assert adapter.provider_name == "openai"


class TestBuildMessages:
    """Tests for _build_messages helper."""

    def test_should_build_basic_messages(self, adapter: OpenAIAdapter) -> None:
        """_build_messages should create system + user messages."""
        prompt = Prompt(system="Be helpful", user="Hello")
        messages = adapter._build_messages(prompt)

        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "Be helpful"}
        assert messages[1] == {"role": "user", "content": "Hello"}

    def test_should_omit_empty_system(self, adapter: OpenAIAdapter) -> None:
        """Empty system prompt should not create a system message."""
        prompt = Prompt(user="Hello only")
        messages = adapter._build_messages(prompt)

        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello only"}

    def test_should_include_context(self, adapter: OpenAIAdapter) -> None:
        """Context items should be interleaved between system and user."""
        prompt = Prompt(
            system="Sys",
            user="User query",
            context=[
                {"role": "assistant", "content": "Prev assistant"},
                {"role": "user", "content": "Prev user"},
            ],
        )
        messages = adapter._build_messages(prompt)

        assert len(messages) == 4
        assert messages[0] == {"role": "system", "content": "Sys"}
        assert messages[1] == {"role": "assistant", "content": "Prev assistant"}
        assert messages[2] == {"role": "user", "content": "Prev user"}
        assert messages[3] == {"role": "user", "content": "User query"}

    def test_should_default_context_role_to_user(self, adapter: OpenAIAdapter) -> None:
        """Context items without a role should default to 'user'."""
        prompt = Prompt(
            user="Final",
            context=[{"content": "No role specified"}],
        )
        messages = adapter._build_messages(prompt)

        assert messages[0] == {"role": "user", "content": "No role specified"}
        assert messages[1] == {"role": "user", "content": "Final"}


class TestMergeConfig:
    """Tests for _merge_config helper."""

    def test_should_return_defaults_when_no_override(self, adapter: OpenAIAdapter) -> None:
        """_merge_config with None should return base defaults."""
        cfg = adapter._merge_config(None)
        assert cfg["model"] == "gpt-4o-mini"
        assert cfg["temperature"] == 0.3
        assert cfg["max_tokens"] == 2000
        assert cfg["timeout_seconds"] == 60.0

    def test_should_override_values(self, adapter: OpenAIAdapter) -> None:
        """Override dict should replace base values."""
        cfg = adapter._merge_config({"temperature": 0.9, "max_tokens": 500})
        assert cfg["temperature"] == 0.9
        assert cfg["max_tokens"] == 500
        assert cfg["model"] == "gpt-4o-mini"  # unchanged

    def test_should_accept_all_override_keys(self, adapter: OpenAIAdapter) -> None:
        """All config keys should be overridable."""
        overrides = {
            "model": "gpt-4o",
            "temperature": 0.1,
            "max_tokens": 100,
            "timeout_seconds": 10.0,
        }
        cfg = adapter._merge_config(overrides)
        assert cfg == overrides


class TestDescribeSchema:
    """Tests for _describe_schema static helper."""

    def test_should_describe_simple_schema(self) -> None:
        """_describe_schema should list field names with types."""
        desc = OpenAIAdapter._describe_schema(_TestSimpleOutput)
        assert "answer (str)" in desc
        assert "score (int)" in desc

    def test_should_describe_complex_schema(self) -> None:
        """_describe_schema should handle list fields."""
        desc = OpenAIAdapter._describe_schema(_TestBrandOutput)
        assert "brand_name (str)" in desc
        assert "positioning (str)" in desc
        assert "key_messages (list)" in desc


class TestInjectJsonInstructions:
    """Tests for _inject_json_instructions helper."""

    def test_should_append_json_instruction(self, adapter: OpenAIAdapter) -> None:
        """System prompt should have JSON instructions appended."""
        prompt = Prompt(system="Be helpful", user="Tell me about Nike")
        result = adapter._inject_json_instructions(prompt, _TestBrandOutput)

        assert "Be helpful" in result.system
        assert "valid JSON object" in result.system
        assert "brand_name" in result.system
        assert result.user == prompt.user
        assert result.context == prompt.context

    def test_should_preserve_original_user_and_context(self, adapter: OpenAIAdapter) -> None:
        """User prompt and context should be unchanged."""
        prompt = Prompt(
            system="Sys",
            user="User",
            context=[{"role": "assistant", "content": "ctx"}],
        )
        result = adapter._inject_json_instructions(prompt, _TestSimpleOutput)

        assert result.user == "User"
        assert result.context == [ChatMessage(role="assistant", content="ctx")]

    def test_should_describe_schema_in_instruction(self, adapter: OpenAIAdapter) -> None:
        """The JSON instruction should include schema field descriptions."""
        prompt = Prompt(system="Base", user="Q")
        result = adapter._inject_json_instructions(prompt, _TestBrandOutput)

        assert "brand_name" in result.system
        assert "positioning" in result.system
        assert "key_messages" in result.system


class TestComplete:
    """Tests for the complete() method."""

    @pytest.mark.asyncio
    async def test_should_return_llm_response(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
        prompt: Prompt,
    ) -> None:
        """complete() should return an LLMResponse with correct fields."""
        adapter._client = mock_openai_client
        result = await adapter.complete(prompt)

        assert isinstance(result, LLMResponse)
        assert result.provider == "openai"
        assert result.model_used == "gpt-4o-mini"
        assert result.tokens_used == 50
        assert result.finish_reason == "stop"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_should_pass_correct_messages(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
        prompt: Prompt,
    ) -> None:
        """complete() should pass correctly formatted messages to the API."""
        adapter._client = mock_openai_client
        await adapter.complete(prompt)

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]

        assert len(messages) == 3  # system + context + user
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == prompt.system
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == prompt.user

    @pytest.mark.asyncio
    async def test_should_use_default_config(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
    ) -> None:
        """complete() should use default model and temperature."""
        adapter._client = mock_openai_client
        await adapter.complete(Prompt(user="test"))

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_should_override_config(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
    ) -> None:
        """complete() should apply config overrides."""
        adapter._client = mock_openai_client
        config = {"model": "gpt-4o", "temperature": 0.9, "max_tokens": 500}
        await adapter.complete(Prompt(user="test"), config=config)

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.9
        assert call_kwargs["max_tokens"] == 500

    @pytest.mark.asyncio
    async def test_should_handle_none_content(
        self,
        adapter: OpenAIAdapter,
        prompt: Prompt,
    ) -> None:
        """complete() should handle None content from API gracefully."""
        mock_response = MagicMock(
            choices=[MagicMock(message=MagicMock(content=None), finish_reason="stop")],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=10, prompt_tokens=5, completion_tokens=5),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.complete(prompt)
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_should_handle_missing_usage(
        self,
        adapter: OpenAIAdapter,
        prompt: Prompt,
    ) -> None:
        """complete() should handle None usage from API."""
        mock_response = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Hi"), finish_reason="stop")],
            model="gpt-4o-mini",
            usage=None,
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.complete(prompt)
        assert result.tokens_used == 0
        assert result.metadata["provider_metadata"]["prompt_tokens"] == 0
        assert result.metadata["provider_metadata"]["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_should_include_metadata(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
        prompt: Prompt,
    ) -> None:
        """complete() should include token metadata."""
        adapter._client = mock_openai_client
        result = await adapter.complete(prompt)

        provider_metadata = result.metadata["provider_metadata"]
        assert "prompt_tokens" in provider_metadata
        assert "completion_tokens" in provider_metadata
        assert provider_metadata["prompt_tokens"] == 30
        assert provider_metadata["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_should_measure_latency(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
        prompt: Prompt,
    ) -> None:
        """complete() should record non-negative latency."""
        adapter._client = mock_openai_client
        result = await adapter.complete(prompt)

        assert result.latency_ms >= 0


class TestCompleteTimeout:
    """Tests for timeout handling in complete()."""

    @pytest.mark.asyncio
    async def test_should_raise_llm_call_error_on_timeout(self, adapter: OpenAIAdapter) -> None:
        """Timeout should raise LLMCallError with retryable=True."""

        async def _slow_call(*_args: Any, **_kwargs: Any) -> MagicMock:
            await asyncio.sleep(1000)
            return MagicMock()

        mock_client = AsyncMock()
        mock_client.chat.completions.create = _slow_call
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(Prompt(user="test"), config={"timeout_seconds": 0.01})

        assert exc_info.value.provider == "openai"
        assert exc_info.value.retryable is True
        assert "timed out" in str(exc_info.value)


class TestCompleteApiErrors:
    """Tests for API error handling in complete()."""

    @pytest.mark.asyncio
    async def test_should_raise_llm_call_error_on_api_failure(
        self,
        adapter: OpenAIAdapter,
    ) -> None:
        """API exception should raise LLMCallError."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("authentication failed"),
        )
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(Prompt(user="test"))

        assert exc_info.value.provider == "openai"
        assert "authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_should_mark_rate_limit_as_retryable(self, adapter: OpenAIAdapter) -> None:
        """Rate limit errors should be marked retryable."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("rate_limit_error: retry after 20s"),
        )
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(Prompt(user="test"))

        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_should_mark_other_errors_non_retryable(self, adapter: OpenAIAdapter) -> None:
        """Non-rate-limit errors should be non-retryable."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Invalid API key"),
        )
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(Prompt(user="test"))

        assert exc_info.value.retryable is False


class TestCompleteStructured:
    """Tests for the complete_structured() method."""

    @pytest.mark.asyncio
    async def test_should_return_parsed_model(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
    ) -> None:
        """complete_structured() should parse JSON into Pydantic model."""
        adapter._client = mock_openai_client
        prompt = Prompt(user="Describe the brand Nike")
        result = await adapter.complete_structured(prompt, _TestBrandOutput)

        assert isinstance(result, _TestBrandOutput)
        assert result.brand_name == "Nike"
        assert result.positioning == "Just Do It"
        assert result.key_messages == ["authenticity", "performance"]

    @pytest.mark.asyncio
    async def test_should_strip_json_code_block(
        self,
        adapter: OpenAIAdapter,
    ) -> None:
        """complete_structured() should strip ```json markdown fences."""
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='```json\n{"answer": "yes", "score": 42}\n```',
                    ),
                    finish_reason="stop",
                )
            ],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=20, prompt_tokens=10, completion_tokens=10),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.complete_structured(
            Prompt(user="test"),
            _TestSimpleOutput,
        )

        assert result.answer == "yes"
        assert result.score == 42

    @pytest.mark.asyncio
    async def test_should_strip_generic_code_block(
        self,
        adapter: OpenAIAdapter,
    ) -> None:
        """complete_structured() should strip ``` markdown fences."""
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='```\n{"answer": "hello", "score": 7}\n```',
                    ),
                    finish_reason="stop",
                )
            ],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=15, prompt_tokens=8, completion_tokens=7),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.complete_structured(
            Prompt(user="test"),
            _TestSimpleOutput,
        )

        assert result.answer == "hello"
        assert result.score == 7

    @pytest.mark.asyncio
    async def test_should_strip_trailing_whitespace(
        self,
        adapter: OpenAIAdapter,
    ) -> None:
        """complete_structured() should handle whitespace around JSON."""
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='   {"answer": "trimmed", "score": 99}   ',
                    ),
                    finish_reason="stop",
                )
            ],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=15, prompt_tokens=8, completion_tokens=7),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.complete_structured(
            Prompt(user="test"),
            _TestSimpleOutput,
        )

        assert result.answer == "trimmed"
        assert result.score == 99

    @pytest.mark.asyncio
    async def test_should_raise_on_invalid_json(self, adapter: OpenAIAdapter) -> None:
        """complete_structured() should raise LLMCallError for invalid JSON."""
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="not valid json"),
                    finish_reason="stop",
                )
            ],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=5, prompt_tokens=3, completion_tokens=2),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete_structured(Prompt(user="test"), _TestSimpleOutput)

        assert exc_info.value.provider == "openai"
        assert exc_info.value.retryable is False
        assert "Failed to parse" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_should_raise_on_schema_validation_failure(
        self,
        adapter: OpenAIAdapter,
    ) -> None:
        """complete_structured() should raise LLMCallError for schema mismatch."""
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content='{"wrong_field": "value"}'),
                    finish_reason="stop",
                )
            ],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=5, prompt_tokens=3, completion_tokens=2),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete_structured(Prompt(user="test"), _TestSimpleOutput)

        assert "Failed to parse" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_should_pass_config_to_complete(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
    ) -> None:
        """complete_structured() should pass config through to complete()."""
        adapter._client = mock_openai_client
        config = {"temperature": 0.1}
        await adapter.complete_structured(
            Prompt(user="test"),
            _TestBrandOutput,
            config=config,
        )

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_should_inject_json_instructions_into_system(
        self,
        adapter: OpenAIAdapter,
        mock_openai_client: AsyncMock,
    ) -> None:
        """complete_structured() should inject JSON instructions into system prompt."""
        adapter._client = mock_openai_client
        prompt = Prompt(system="Be concise", user="test")
        await adapter.complete_structured(prompt, _TestBrandOutput)

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]

        # System message should have JSON instructions appended
        system_msg = messages[0]["content"]
        assert "Be concise" in system_msg
        assert "valid JSON object" in system_msg

    @pytest.mark.asyncio
    async def test_should_include_raw_content_in_error(self, adapter: OpenAIAdapter) -> None:
        """Parse error should include raw content snippet in context."""
        bad_content = "not json at all"
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content=bad_content),
                    finish_reason="stop",
                )
            ],
            model="gpt-4o-mini",
            usage=MagicMock(total_tokens=5, prompt_tokens=3, completion_tokens=2),
        )
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete_structured(Prompt(user="test"), _TestSimpleOutput)

        assert exc_info.value.context is not None
