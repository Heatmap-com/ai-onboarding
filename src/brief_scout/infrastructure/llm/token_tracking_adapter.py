"""Token-tracking wrapper for any LLM adapter.

Adds prompt/completion token counting (via tiktoken) and cost estimation to
an underlying LLM port without changing adapter implementations. Enabled in
``main.py`` when ``BRIEF_SCOUT_TRACK_TOKENS`` is set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import LLMPort, LLMResponse, Prompt, T


# Rough per-1M-token pricing (USD) for cost estimates. Update as provider
# pricing changes. Unknown models fall back to gpt-4o-mini.
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-opus": (15.00, 75.00),
    "moonshot-v1-8k": (0.50, 0.50),
    "moonshot-v1-32k": (1.00, 1.00),
}


def _rates_for(model: str) -> tuple[float, float]:
    """Return (input_rate, output_rate) for a model name."""
    lower = model.lower()
    for key, rates in _PRICING.items():
        if key in lower:
            return rates
    return _PRICING["gpt-4o-mini"]


@dataclass
class TokenUsageRecord:
    """Token counts for a single LLM call."""

    call_number: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        input_rate, output_rate = _rates_for(self.model)
        return (
            self.input_tokens * input_rate / 1_000_000
            + self.output_tokens * output_rate / 1_000_000
        )


@dataclass
class TokenUsage:
    """Aggregated token usage across all tracked LLM calls."""

    records: list[TokenUsageRecord] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)

    @property
    def estimated_cost_usd(self) -> float:
        return sum(r.estimated_cost_usd for r in self.records)

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines: list[str] = []
        lines.append(
            f"{'Call':>4} {'Provider':<10} {'Model':<25} "
            f"{'Input':>8} {'Output':>8} {'Total':>8} {'Cost (USD)':>12}"
        )
        lines.append("-" * len(lines[0]))
        for record in self.records:
            lines.append(
                f"{record.call_number:>4} {record.provider:<10} {record.model:<25} "
                f"{record.input_tokens:>8} {record.output_tokens:>8} "
                f"{record.total_tokens:>8} ${record.estimated_cost_usd:>11.6f}"
            )
        lines.append("-" * len(lines[0]))
        lines.append(
            f"{'TOTAL':>42} {self.total_input_tokens:>8} {self.total_output_tokens:>8} "
            f"{self.total_tokens:>8} ${self.estimated_cost_usd:>11.6f}"
        )
        return "\n".join(lines)


class TokenTrackingLLM:
    """Wraps an LLM adapter and counts input/output tokens with tiktoken.

    The wrapper transparently delegates every call to the underlying adapter,
    then records token counts based on the prompt text and the returned
    structured/text output.

    Args:
        adapter: The real LLM adapter to wrap.
        model: Model name used to pick a tiktoken encoding and pricing.
    """

    def __init__(self, adapter: LLMPort, model: str = "gpt-4o-mini") -> None:
        """Initialize the token-tracking wrapper."""
        self._adapter = adapter
        self._model = model
        self._usage = TokenUsage()
        self._counter = 0
        self._encoder = self._load_encoder(model)

    @staticmethod
    def _load_encoder(model: str) -> Any:
        """Load the best available tiktoken encoder for ``model``."""
        try:
            import tiktoken

            try:
                return tiktoken.encoding_for_model(model)
            except KeyError:
                return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    @property
    def provider_name(self) -> str:
        """Return the underlying provider identifier."""
        return str(getattr(self._adapter, "provider_name", "unknown"))

    @property
    def token_usage(self) -> TokenUsage:
        """Return accumulated token usage."""
        return self._usage

    def _count_text(self, text: str) -> int:
        """Count tokens in a plain text string."""
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        # Fallback heuristic: ~4 characters per token.
        return max(1, len(text) // 4)

    def _count_prompt(self, prompt: Prompt) -> int:
        """Count tokens in a standardized prompt."""
        total = self._count_text(prompt.system) + self._count_text(prompt.user)
        for message in prompt.context:
            total += self._count_text(str(message.role))
            total += self._count_text(str(message.content))
        return total

    def _record(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record a single call's token usage."""
        self._counter += 1
        self._usage.records.append(
            TokenUsageRecord(
                call_number=self._counter,
                provider=self.provider_name,
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a completion and record token usage."""
        response = await self._adapter.complete(prompt, config)
        input_tokens = self._count_prompt(prompt)
        output_tokens = self._count_text(response.content)
        self._record(input_tokens, output_tokens)
        return response

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute a structured completion and record token usage."""
        result = await self._adapter.complete_structured(
            prompt,
            output_schema,
            config,
        )
        input_tokens = self._count_prompt(prompt)
        output_tokens = self._count_text(result.model_dump_json())
        self._record(input_tokens, output_tokens)
        return result
