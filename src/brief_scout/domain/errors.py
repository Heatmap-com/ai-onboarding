"""Custom exception hierarchy for Brief Scout.

All domain-specific exceptions inherit from BriefScoutError, allowing
callers to catch any application-specific error with a single handler.
Each subclass adds context relevant to its specific error domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brief_scout.domain.models.research import ResearchBundle


class BriefScoutError(Exception):
    """Base exception for all Brief Scout errors.

    Attributes:
        context: Arbitrary dictionary of contextual data for debugging.
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize with message and optional context.

        Args:
            message: Human-readable error description.
            context: Optional dictionary of debugging context.
        """
        super().__init__(message)
        self.context = context or {}


class LLMCallError(BriefScoutError):
    """LLM call failed — timeout, rate limit, parse error, etc.

    Attributes:
        provider: The LLM provider that failed (e.g., 'fake', 'kimi').
        retryable: Whether the error is transient and may succeed on retry.
    """

    def __init__(
        self,
        message: str,
        provider: str = "",
        retryable: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize LLM call error.

        Args:
            message: Error description.
            provider: The LLM provider identifier.
            retryable: Whether the error may be transient.
            **kwargs: Additional context data.
        """
        super().__init__(message, kwargs)
        self.provider = provider
        self.retryable = retryable


class ConfigError(BriefScoutError):
    """Configuration loading or validation error.

    Raised when YAML files are malformed, required settings are missing,
    or environment variable interpolation fails.
    """

    pass


class ValidationError(BriefScoutError):
    """Data validation error.

    Raised when input data fails Pydantic validation or business rule checks.
    """

    pass


class ResearchPipelineError(BriefScoutError):
    """One or more research calls failed during the research phase.

    The pipeline continues even if individual calls fail — partial
    results are available via the partial_results attribute.

    Attributes:
        partial_results: The ResearchBundle containing any successful results.
    """

    def __init__(
        self,
        message: str,
        partial_results: ResearchBundle | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize research pipeline error.

        Args:
            message: Error description.
            partial_results: Any successfully completed research results.
            **kwargs: Additional context data.
        """
        super().__init__(message, kwargs)
        self.partial_results = partial_results


class SynthesisError(BriefScoutError):
    """Brief synthesis failed.

    Raised when the synthesis use case cannot produce a valid Brief
    from the research results and intake data.
    """

    pass
