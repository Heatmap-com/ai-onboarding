"""Simple in-memory circuit breaker for LLM provider calls."""

from __future__ import annotations

import time
from typing import Any


class CircuitBreaker:
    """Open/closed circuit breaker for external service calls.

    Tracks consecutive failures and temporarily blocks new attempts
    after a threshold is reached, recovering after a timeout.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        """Initialize the breaker.

        Args:
            failure_threshold: Consecutive failures before opening the circuit.
            recovery_timeout: Seconds to wait before allowing a probe call.
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._last_failure_time: float | None = None
        self._state = "closed"

    @property
    def state(self) -> str:
        """Return current state: ``closed``, ``open``, or ``half_open``."""
        if (
            self._state == "open"
            and self._last_failure_time is not None
            and (time.monotonic() - self._last_failure_time >= self._recovery_timeout)
        ):
            self._state = "half_open"
        return self._state

    def raise_if_open(self) -> None:
        """Raise CircuitBreakerOpenError if the circuit is currently open."""
        if self.state == "open":
            raise CircuitBreakerOpenError("LLM provider circuit breaker is open")

    def record_success(self) -> None:
        """Reset failure count on a successful call."""
        self._failures = 0
        self._last_failure_time = None
        self._state = "closed"

    def record_failure(self) -> None:
        """Increment failure count and open the circuit if threshold reached."""
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self._failure_threshold:
            self._state = "open"


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        """Initialize with message and optional context."""
        super().__init__(message)
        self.context = kwargs
