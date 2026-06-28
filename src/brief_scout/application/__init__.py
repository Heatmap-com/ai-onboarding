"""Application layer — use cases and DTOs.

The application layer orchestrates business flows by coordinating
domain services and ports. It is framework-agnostic and contains
no business rules (those live in the domain layer).
"""

from brief_scout.application.dto import (
    BriefResponse,
    ChatResponse,
    HealthResponse,
    MessageRequest,
    SessionResponse,
)
from brief_scout.application.use_cases import (
    IntakeResponse,
    IntakeUseCase,
    ResearchUseCase,
    SynthesisUseCase,
)

__all__ = [
    # DTOs
    "BriefResponse",
    "ChatResponse",
    "HealthResponse",
    "MessageRequest",
    "SessionResponse",
    # Use cases
    "IntakeResponse",
    "IntakeUseCase",
    "ResearchUseCase",
    "SynthesisUseCase",
]
