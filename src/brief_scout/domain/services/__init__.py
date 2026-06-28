"""Domain services — business logic that operates on domain models.

Services contain business rules that don't naturally belong within
a single entity or value object. They orchestrate domain operations
while remaining framework-agnostic.
"""

from brief_scout.domain.services.completeness_checker import (
    CompletenessChecker,
    CompletenessResult,
)
from brief_scout.domain.services.intake_data_merger import IntakeDataMerger

__all__ = [
    "CompletenessChecker",
    "CompletenessResult",
    "IntakeDataMerger",
]
