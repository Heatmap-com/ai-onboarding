"""Application use cases — business flow orchestration.

Per SPEC 6 — Each use case encapsulates a single business flow:
- IntakeUseCase: conversational data collection
- ResearchUseCase: 5 parallel research calls
- SynthesisUseCase: brief generation from research
"""

from brief_scout.application.use_cases.intake_use_case import (
    IntakeResponse,
    IntakeUseCase,
)
from brief_scout.application.use_cases.research_use_case import ResearchUseCase
from brief_scout.application.use_cases.synthesis_use_case import SynthesisUseCase

__all__ = [
    "IntakeResponse",
    "IntakeUseCase",
    "ResearchUseCase",
    "SynthesisUseCase",
]
