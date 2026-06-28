"""Comprehensive unit tests for KimiAdapter.

Tests the Kimi (Moonshot AI) LLM adapter which uses the OpenAI SDK
with a custom base_url. All external API calls are mocked.

Target: 90% coverage.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.infrastructure.llm.kimi_adapter import KimiAdapter

# ---------------------------------------------------------------------------
# Test schema for structured output tests
# ---------------------------------------------------------------------------


class _TestBrandResult(BaseModel):
    """Test Pydantic model for structured output parsing."""

    brand_name: str
    positioning: str


class _TestComplexSchema(BaseModel):
    """Test schema with multiple field types."""

    name: str
    score: float
    tags: list[str]


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> KimiAdapter:
    """Provide a KimiAdapter with a dummy API key (no network calls)."""
    return KimiAdapter(api_key="test-key-sk-123456")


@pytest.fixture
def mock_kimi_client() -> MagicMock:
    """Provide a mocked AsyncOpenAI client that returns a valid response."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"brand_name": "Nike", "positioning": "Just Do It"}'
                    ),
                    finish_reason="stop",
                )
            ],
            model="moonshot-v1-8k",
            usage=MagicMock(
                total_tokens=50,
                prompt_tokens=30,
                completion_tokens=20,
            ),
        )
    )
    return mock


@pytest.fixture
def mock_kimi_client_plain_text() -> MagicMock:
    """Provide a mocked client that returns plain text (non-JSON)."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="Hello from Kimi!"),
                    finish_reason="stop",
                )
            ],
            model="moonshot-v1-8k",
            usage=MagicMock(
                total_tokens=10,
                prompt_tokens=5,
                completion_tokens=5,
            ),
        )
    )
    return mock


@pytest.fixture
def mock_kimi_client_markdown_json() -> MagicMock:
    """Provide a mocked client that returns JSON wrapped in markdown fences."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='```json\n{"brand_name": "Adidas", "positioning": "Impossible is Nothing"}\n```'
                    ),
                    finish_reason="stop",
                )
            ],
            model="moonshot-v1-8k",
            usage=MagicMock(
                total_tokens=40,
                prompt_tokens=20,
                completion_tokens=20,
            ),
        )
    )
    return mock


@pytest.fixture
def mock_kimi_client_timeout() -> MagicMock:
    """Provide a mocked client that raises TimeoutError."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(side_effect=TimeoutError("Request timed out"))
    return mock


@pytest.fixture
def mock_kimi_client_api_error() -> MagicMock:
    """Provide a mocked client that raises a generic API error."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(side_effect=Exception("401 Invalid API key"))
    return mock


@pytest.fixture
def mock_kimi_client_rate_limit() -> MagicMock:
    """Provide a mocked client that raises a rate limit error."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(
        side_effect=Exception("rate_limit_exceeded: Rate limit reached")
    )
    return mock


@pytest.fixture
def mock_kimi_client_no_usage() -> MagicMock:
    """Provide a mocked client that returns response without usage data."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="No usage data here."),
                    finish_reason="stop",
                )
            ],
            model="moonshot-v1-8k",
            usage=None,
        )
    )
    return mock


# ============================================================================
# Construction & Configuration Tests
# ============================================================================


class TestKimiAdapterConstruction:
    """Tests for adapter initialization and configuration."""

    def test_default_construction(self) -> None:
        """Adapter should construct with sensible defaults."""
        a = KimiAdapter(api_key="test-key")
        assert a._api_key == "test-key"
        assert a._model == "moonshot-v1-8k"
        assert a._base_url == KimiAdapter.DEFAULT_BASE_URL
        assert a._temperature == 0.3
        assert a._max_tokens == 2000
        assert a._timeout == 60.0
        assert a._client is None  # Lazy init

    def test_custom_model(self) -> None:
        """Adapter should accept custom model identifier."""
        a = KimiAdapter(api_key="test-key", model="moonshot-v1-128k")
        assert a._model == "moonshot-v1-128k"

    def test_custom_base_url(self) -> None:
        """Adapter should accept custom base_url."""
        custom_url = "https://custom.moonshot.cn/v1"
        a = KimiAdapter(api_key="test-key", base_url=custom_url)
        assert a._base_url == custom_url

    def test_default_base_url_constant(self) -> None:
        """DEFAULT_BASE_URL should be the official Kimi endpoint."""
        assert KimiAdapter.DEFAULT_BASE_URL == "https://api.moonshot.cn/v1"

    def test_custom_temperature_and_max_tokens(self) -> None:
        """Adapter should accept custom temperature and max_tokens."""
        a = KimiAdapter(api_key="test-key", temperature=0.7, max_tokens=4096)
        assert a._temperature == 0.7
        assert a._max_tokens == 4096

    def test_custom_timeout(self) -> None:
        """Adapter should accept custom timeout."""
        a = KimiAdapter(api_key="test-key", timeout_seconds=120.0)
        assert a._timeout == 120.0

    def test_telemetry_option(self) -> None:
        """Adapter should accept optional telemetry object."""
        telemetry = MagicMock()
        a = KimiAdapter(api_key="test-key", telemetry=telemetry)
        assert a._telemetry is telemetry

    def test_api_key_from_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Adapter should read API key from KIMI_API_KEY env var."""
        monkeypatch.setenv("KIMI_API_KEY", "env-var-key")
        a = KimiAdapter()
        assert a._api_key == "env-var-key"

    def test_api_key_explicit_overrides_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit api_key parameter should override env var."""
        monkeypatch.setenv("KIMI_API_KEY", "env-var-key")
        a = KimiAdapter(api_key="explicit-key")
        assert a._api_key == "explicit-key"

    def test_empty_api_key_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Adapter should have empty api_key when no env var or param."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        a = KimiAdapter()
        assert a._api_key == ""

    def test_provider_name(self, adapter: KimiAdapter) -> None:
        """provider_name should return 'kimi'."""
        assert adapter.provider_name == "kimi"

    def test_lazy_client_initialization(self, adapter: KimiAdapter) -> None:
        """Client should be None until _get_client is called."""
        assert adapter._client is None


# ============================================================================
# complete() Tests
# ============================================================================


class TestKimiAdapterComplete:
    """Tests for the complete() method."""

    @pytest.mark.asyncio
    async def test_complete_returns_llm_response(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should return an LLMResponse object."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(system="You are helpful.", user="Say hello.")

        response = await adapter.complete(prompt)

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from Kimi!"
        assert response.provider == "kimi"
        assert response.model_used == "moonshot-v1-8k"
        assert response.tokens_used == 10
        assert response.finish_reason == "stop"
        assert response.latency_ms >= 0
        assert "prompt_tokens" in response.metadata
        assert "completion_tokens" in response.metadata
        assert response.metadata["prompt_tokens"] == 5
        assert response.metadata["completion_tokens"] == 5

    @pytest.mark.asyncio
    async def test_complete_with_no_system_prompt(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should work without a system prompt."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(user="Just a user message.")

        response = await adapter.complete(prompt)

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from Kimi!"

    @pytest.mark.asyncio
    async def test_complete_with_context(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should include context messages."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(
            system="You are helpful.",
            user="What about that?",
            context=[
                {"role": "user", "content": "Tell me about Nike."},
                {"role": "assistant", "content": "Nike is a sportswear brand."},
            ],
        )

        response = await adapter.complete(prompt)

        assert isinstance(response, LLMResponse)
        # Verify the client was called
        mock_kimi_client_plain_text.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_passes_correct_model(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should pass the model to the API."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(user="Test.")

        await adapter.complete(prompt)

        call_kwargs = mock_kimi_client_plain_text.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "moonshot-v1-8k"

    @pytest.mark.asyncio
    async def test_complete_passes_correct_temperature_and_max_tokens(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should pass temperature and max_tokens to the API."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(user="Test.")

        await adapter.complete(prompt)

        call_kwargs = mock_kimi_client_plain_text.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_complete_with_config_override(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should allow config overrides."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(user="Test.")
        config = {"temperature": 0.9, "max_tokens": 500, "model": "moonshot-v1-32k"}

        await adapter.complete(prompt, config)

        call_kwargs = mock_kimi_client_plain_text.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.9
        assert call_kwargs["max_tokens"] == 500
        assert call_kwargs["model"] == "moonshot-v1-32k"

    @pytest.mark.asyncio
    async def test_complete_with_empty_config(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should use defaults when config is None."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(user="Test.")

        await adapter.complete(prompt, None)

        call_kwargs = mock_kimi_client_plain_text.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_complete_response_without_usage(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_no_usage: MagicMock,
    ) -> None:
        """complete() should handle responses without usage data."""
        adapter._client = mock_kimi_client_no_usage
        prompt = Prompt(user="Test.")

        response = await adapter.complete(prompt)

        assert response.tokens_used == 0
        assert response.metadata["prompt_tokens"] == 0
        assert response.metadata["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_complete_response_with_empty_content(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """complete() should handle empty content gracefully."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content=None),
                        finish_reason="length",
                    )
                ],
                model="moonshot-v1-8k",
                usage=MagicMock(total_tokens=100),
            )
        )
        adapter._client = mock_client
        prompt = Prompt(user="Test.")

        response = await adapter.complete(prompt)

        assert response.content == ""
        assert response.finish_reason == "length"

    @pytest.mark.asyncio
    async def test_complete_passes_base_url_in_metadata(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_plain_text: MagicMock,
    ) -> None:
        """complete() should include base_url in response metadata."""
        adapter._client = mock_kimi_client_plain_text
        prompt = Prompt(user="Test.")

        response = await adapter.complete(prompt)

        assert response.metadata["base_url"] == KimiAdapter.DEFAULT_BASE_URL


# ============================================================================
# complete() Error Handling Tests
# ============================================================================


class TestKimiAdapterCompleteErrors:
    """Tests for error handling in complete()."""

    @pytest.mark.asyncio
    async def test_timeout_raises_llm_call_error(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_timeout: MagicMock,
    ) -> None:
        """Timeout should raise LLMCallError with retryable=True."""
        adapter._client = mock_kimi_client_timeout
        prompt = Prompt(user="Test timeout.")

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(prompt)

        assert "timed out" in str(exc_info.value).lower()
        assert exc_info.value.provider == "kimi"
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_api_error_raises_llm_call_error(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_api_error: MagicMock,
    ) -> None:
        """API error should raise LLMCallError with retryable=False (auth error)."""
        adapter._client = mock_kimi_client_api_error
        prompt = Prompt(user="Test error.")

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(prompt)

        assert "Kimi API error" in str(exc_info.value)
        assert exc_info.value.provider == "kimi"
        assert exc_info.value.retryable is False  # 401 is not retryable

    @pytest.mark.asyncio
    async def test_rate_limit_error_is_retryable(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_rate_limit: MagicMock,
    ) -> None:
        """Rate limit error should be marked as retryable."""
        adapter._client = mock_kimi_client_rate_limit
        prompt = Prompt(user="Test rate limit.")

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(prompt)

        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_timeout_in_error_message_is_retryable(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """Error containing 'timeout' in message should be retryable."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection timeout after 30s")
        )
        adapter._client = mock_client
        prompt = Prompt(user="Test.")

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete(prompt)

        assert exc_info.value.retryable is True


# ============================================================================
# complete_structured() Tests
# ============================================================================


class TestKimiAdapterCompleteStructured:
    """Tests for the complete_structured() method."""

    @pytest.mark.asyncio
    async def test_complete_structured_returns_parsed_model(
        self,
        adapter: KimiAdapter,
        mock_kimi_client: MagicMock,
    ) -> None:
        """complete_structured() should return a parsed Pydantic model."""
        adapter._client = mock_kimi_client
        prompt = Prompt(
            system="You are a brand analyst.",
            user="Analyze Nike.",
        )

        result = await adapter.complete_structured(prompt, _TestBrandResult)

        assert isinstance(result, _TestBrandResult)
        assert result.brand_name == "Nike"
        assert result.positioning == "Just Do It"

    @pytest.mark.asyncio
    async def test_complete_structured_strips_markdown_fences(
        self,
        adapter: KimiAdapter,
        mock_kimi_client_markdown_json: MagicMock,
    ) -> None:
        """complete_structured() should strip ```json fences before parsing."""
        adapter._client = mock_kimi_client_markdown_json
        prompt = Prompt(user="Analyze Adidas.")

        result = await adapter.complete_structured(prompt, _TestBrandResult)

        assert isinstance(result, _TestBrandResult)
        assert result.brand_name == "Adidas"
        assert result.positioning == "Impossible is Nothing"

    @pytest.mark.asyncio
    async def test_complete_structured_injects_json_instructions(
        self,
        adapter: KimiAdapter,
        mock_kimi_client: MagicMock,
    ) -> None:
        """complete_structured() should inject JSON instructions into system prompt."""
        adapter._client = mock_kimi_client
        prompt = Prompt(
            system="You are a brand analyst.",
            user="Analyze Nike.",
        )

        await adapter.complete_structured(prompt, _TestBrandResult)

        # Verify the API was called with JSON instructions in system prompt
        call_kwargs = mock_kimi_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "JSON" in system_msg["content"]
        assert "brand_name" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_complete_structured_with_complex_schema(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """complete_structured() should handle complex schemas with lists."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(
                                {
                                    "name": "Test Product",
                                    "score": 4.5,
                                    "tags": ["innovative", "premium"],
                                }
                            )
                        ),
                        finish_reason="stop",
                    )
                ],
                model="moonshot-v1-8k",
                usage=MagicMock(total_tokens=30),
            )
        )
        adapter._client = mock_client
        prompt = Prompt(user="Analyze this product.")

        result = await adapter.complete_structured(prompt, _TestComplexSchema)

        assert isinstance(result, _TestComplexSchema)
        assert result.name == "Test Product"
        assert result.score == 4.5
        assert result.tags == ["innovative", "premium"]

    @pytest.mark.asyncio
    async def test_complete_structured_invalid_json_raises(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """complete_structured() should raise LLMCallError for invalid JSON."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="This is not JSON at all!"),
                        finish_reason="stop",
                    )
                ],
                model="moonshot-v1-8k",
                usage=MagicMock(total_tokens=10),
            )
        )
        adapter._client = mock_client
        prompt = Prompt(user="Test invalid JSON.")

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete_structured(prompt, _TestBrandResult)

        assert "Failed to parse structured output" in str(exc_info.value)
        assert exc_info.value.provider == "kimi"
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_complete_structured_validation_error_raises(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """complete_structured() should raise LLMCallError for validation failures."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"brand_name": "Nike"}'  # Missing required "positioning"
                        ),
                        finish_reason="stop",
                    )
                ],
                model="moonshot-v1-8k",
                usage=MagicMock(total_tokens=10),
            )
        )
        adapter._client = mock_client
        prompt = Prompt(user="Test validation error.")

        with pytest.raises(LLMCallError) as exc_info:
            await adapter.complete_structured(prompt, _TestBrandResult)

        assert "Failed to parse structured output" in str(exc_info.value)
        assert exc_info.value.provider == "kimi"
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_complete_structured_with_config_override(
        self,
        adapter: KimiAdapter,
        mock_kimi_client: MagicMock,
    ) -> None:
        """complete_structured() should pass config overrides through."""
        adapter._client = mock_kimi_client
        prompt = Prompt(user="Test.")
        config = {"temperature": 0.1, "model": "moonshot-v1-32k"}

        await adapter.complete_structured(prompt, _TestBrandResult, config)

        call_kwargs = mock_kimi_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["model"] == "moonshot-v1-32k"


# ============================================================================
# _build_messages() Tests
# ============================================================================


class TestKimiAdapterBuildMessages:
    """Tests for the _build_messages() helper."""

    def test_build_messages_with_system(self, adapter: KimiAdapter) -> None:
        """_build_messages should include system message when present."""
        prompt = Prompt(system="You are helpful.", user="Hello.")
        messages = adapter._build_messages(prompt)

        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[1] == {"role": "user", "content": "Hello."}

    def test_build_messages_without_system(self, adapter: KimiAdapter) -> None:
        """_build_messages should omit system message when empty."""
        prompt = Prompt(user="Hello.")
        messages = adapter._build_messages(prompt)

        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello."}

    def test_build_messages_with_context(self, adapter: KimiAdapter) -> None:
        """_build_messages should include context messages in order."""
        prompt = Prompt(
            system="You are helpful.",
            user="Final question.",
            context=[
                {"role": "user", "content": "First message."},
                {"role": "assistant", "content": "First response."},
            ],
        )
        messages = adapter._build_messages(prompt)

        assert len(messages) == 4
        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[1] == {"role": "user", "content": "First message."}
        assert messages[2] == {"role": "assistant", "content": "First response."}
        assert messages[3] == {"role": "user", "content": "Final question."}

    def test_build_messages_context_defaults_role_to_user(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """_build_messages should default context role to 'user'."""
        prompt = Prompt(
            user="Final question.",
            context=[{"content": "No role specified."}],
        )
        messages = adapter._build_messages(prompt)

        assert messages[0] == {"role": "user", "content": "No role specified."}

    def test_build_messages_empty_prompt(self, adapter: KimiAdapter) -> None:
        """_build_messages should handle empty prompt fields."""
        prompt = Prompt()
        messages = adapter._build_messages(prompt)

        # Should still have the user message even if empty
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": ""}


# ============================================================================
# _merge_config() Tests
# ============================================================================


class TestKimiAdapterMergeConfig:
    """Tests for the _merge_config() helper."""

    def test_merge_config_with_no_override(self, adapter: KimiAdapter) -> None:
        """_merge_config should return defaults when no override given."""
        result = adapter._merge_config(None)

        assert result["model"] == "moonshot-v1-8k"
        assert result["temperature"] == 0.3
        assert result["max_tokens"] == 2000
        assert result["timeout_seconds"] == 60.0

    def test_merge_config_with_override(self, adapter: KimiAdapter) -> None:
        """_merge_config should apply overrides."""
        result = adapter._merge_config({"temperature": 0.9, "max_tokens": 100})

        assert result["temperature"] == 0.9
        assert result["max_tokens"] == 100
        assert result["model"] == "moonshot-v1-8k"  # Unchanged

    def test_merge_config_empty_dict(self, adapter: KimiAdapter) -> None:
        """_merge_config should return defaults with empty dict."""
        result = adapter._merge_config({})

        assert result["model"] == "moonshot-v1-8k"
        assert result["temperature"] == 0.3


# ============================================================================
# _inject_json_instructions() Tests
# ============================================================================


class TestKimiAdapterInjectJson:
    """Tests for the _inject_json_instructions() helper."""

    def test_inject_json_appends_instructions(self, adapter: KimiAdapter) -> None:
        """Should append JSON instructions to system prompt."""
        prompt = Prompt(system="You are helpful.", user="Extract data.")
        result = adapter._inject_json_instructions(prompt, _TestBrandResult)

        assert "You are helpful." in result.system
        assert "JSON" in result.system
        assert "brand_name" in result.system
        assert result.user == "Extract data."

    def test_inject_json_preserves_user_and_context(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """Should preserve user message and context."""
        prompt = Prompt(
            system="You are helpful.",
            user="Extract data.",
            context=[{"role": "user", "content": "Context."}],
        )
        result = adapter._inject_json_instructions(prompt, _TestBrandResult)

        assert result.user == "Extract data."
        assert result.context == [{"role": "user", "content": "Context."}]

    def test_inject_json_includes_schema_fields(self, adapter: KimiAdapter) -> None:
        """JSON instructions should mention schema field names."""
        prompt = Prompt(system="You are helpful.", user="Test.")
        result = adapter._inject_json_instructions(prompt, _TestBrandResult)

        assert "brand_name" in result.system
        assert "positioning" in result.system


# ============================================================================
# _describe_schema() Tests
# ============================================================================


class TestKimiAdapterDescribeSchema:
    """Tests for the _describe_schema() static method."""

    def test_describe_simple_schema(self) -> None:
        """Should describe simple schema fields."""
        desc = KimiAdapter._describe_schema(_TestBrandResult)

        assert "brand_name" in desc
        assert "positioning" in desc

    def test_describe_complex_schema(self) -> None:
        """Should describe complex schema with various types."""
        desc = KimiAdapter._describe_schema(_TestComplexSchema)

        assert "name" in desc
        assert "score" in desc
        assert "tags" in desc

    def test_describe_returns_string(self) -> None:
        """Should return a string."""
        desc = KimiAdapter._describe_schema(_TestBrandResult)

        assert isinstance(desc, str)
        assert len(desc) > 0


# ============================================================================
# _get_client() Tests
# ============================================================================


class TestKimiAdapterGetClient:
    """Tests for the _get_client() method."""

    def _mock_openai_module(self, mock_async_openai_cls: MagicMock) -> MagicMock:
        """Build a fake ``openai`` module with the given AsyncOpenAI class."""
        mock_module = MagicMock()
        mock_module.AsyncOpenAI = mock_async_openai_cls
        return mock_module

    def test_get_client_creates_instance(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """_get_client should create AsyncOpenAI with correct params."""
        mock_async_openai = MagicMock()
        mock_instance = MagicMock()
        mock_async_openai.return_value = mock_instance

        with patch.dict(
            "sys.modules",
            {"openai": self._mock_openai_module(mock_async_openai)},
        ):
            client = adapter._get_client()

        assert client is mock_instance
        mock_async_openai.assert_called_once_with(
            api_key="test-key-sk-123456",
            base_url=KimiAdapter.DEFAULT_BASE_URL,
        )

    def test_get_client_caches_instance(
        self,
        adapter: KimiAdapter,
    ) -> None:
        """_get_client should cache the client instance."""
        mock_async_openai = MagicMock()
        mock_instance = MagicMock()
        mock_async_openai.return_value = mock_instance

        with patch.dict(
            "sys.modules",
            {"openai": self._mock_openai_module(mock_async_openai)},
        ):
            client1 = adapter._get_client()
            client2 = adapter._get_client()

        assert client1 is client2
        mock_async_openai.assert_called_once()  # Only created once

    def test_get_client_with_custom_base_url(self) -> None:
        """_get_client should use custom base_url if provided."""
        mock_async_openai = MagicMock()
        custom_url = "https://custom.moonshot.cn/v2"
        adapter = KimiAdapter(api_key="test-key", base_url=custom_url)

        with patch.dict(
            "sys.modules",
            {"openai": self._mock_openai_module(mock_async_openai)},
        ):
            adapter._get_client()

        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            base_url=custom_url,
        )

    def test_get_client_with_empty_api_key(self) -> None:
        """_get_client should handle empty API key."""
        mock_async_openai = MagicMock()
        adapter = KimiAdapter(api_key="")

        with patch.dict(
            "sys.modules",
            {"openai": self._mock_openai_module(mock_async_openai)},
        ):
            adapter._get_client()

        mock_async_openai.assert_called_once_with(
            api_key="",
            base_url=KimiAdapter.DEFAULT_BASE_URL,
        )
