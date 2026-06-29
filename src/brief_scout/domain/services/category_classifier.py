"""Category classifier for research prompts.

Infers a high-level product category from intake data. When an LLM port is
available, it uses a structured-output classifier over a configurable category
list; otherwise it falls back to a keyword map so tests and offline usage keep
working without a live LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort


DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "apparel / footwear": [
        "shoe",
        "shoes",
        "sneaker",
        "apparel",
        "clothing",
        "fashion",
        "wear",
        "footwear",
        "athletic",
        "sportswear",
    ],
    "technology / software": [
        "software",
        "app",
        "platform",
        "tech",
        "technology",
        "saas",
        "cloud",
        "ai",
        "digital",
    ],
    "food & beverage": [
        "food",
        "beverage",
        "drink",
        "restaurant",
        "coffee",
        "snack",
        "organic",
        "nutrition",
    ],
    "health & wellness": [
        "health",
        "wellness",
        "fitness",
        "gym",
        "supplement",
        "vitamin",
        "mental health",
        "wellbeing",
    ],
    "finance": [
        "finance",
        "banking",
        "investment",
        "crypto",
        "payment",
        "insurance",
        "fintech",
        "money",
    ],
}

DEFAULT_CATEGORIES: list[str] = list(DEFAULT_KEYWORDS.keys()) + ["general"]


class CategoryResult(BaseModel):
    """Structured result from the LLM category classifier."""

    category: str = Field(
        ...,
        description="The most relevant product category for the brand.",
    )

    @field_validator("category")
    @classmethod
    def _lowercase_category(cls, value: str) -> str:
        return value.lower()


class CategoryClassifier:
    """Category inference using an optional LLM with keyword fallback."""

    def __init__(
        self,
        categories: list[str] | None = None,
        keywords: dict[str, list[str]] | None = None,
        llm: StructuredCompletionPort | None = None,
    ) -> None:
        """Initialize the classifier.

        Args:
            categories: Allowed category labels. Defaults to the keyword-map keys
                plus ``"general"``.
            keywords: Optional keyword map for fallback classification.
            llm: Optional structured-completion LLM port. When provided, the
                classifier uses a structured prompt; otherwise it falls back to
                keyword matching.
        """
        self._categories = categories or DEFAULT_CATEGORIES
        self._keywords = keywords or DEFAULT_KEYWORDS
        self._llm = llm

    async def classify(self, intake_data: IntakeData) -> str:
        """Infer a category from intake data.

        Args:
            intake_data: Structured intake data.

        Returns:
            Inferred category string, or ``"general"`` when no match is found.
        """
        if self._llm is not None:
            category = await self._classify_with_llm(intake_data)
            if category in self._categories:
                return category

        return self._classify_with_keywords(intake_data)

    async def _classify_with_llm(self, intake_data: IntakeData) -> str:
        """Classify using a structured LLM call."""
        if self._llm is None:
            return "general"
        from brief_scout.domain.ports import Prompt

        categories_text = "\n".join(f"- {c}" for c in self._categories)
        prompt = Prompt(
            system=(
                "You are a product category classifier. Pick the single best "
                "category for the brand described below from the provided list. "
                "Respond with only the category name."
            ),
            user=(
                f"Brand: {intake_data.brand_name}\n"
                f"Competitors: {', '.join(intake_data.competitors)}\n"
                f"Target customer: {intake_data.target_customer}\n\n"
                f"Categories:\n{categories_text}\n\nCategory:"
            ),
        )
        try:
            result = await self._llm.complete_structured(prompt, CategoryResult)
            return result.category
        except Exception:
            return "general"

    def _classify_with_keywords(self, intake_data: IntakeData) -> str:
        """Fallback keyword-based classification."""
        brand = intake_data.brand_name.lower()
        competitors = " ".join(c.lower() for c in intake_data.competitors)
        target = intake_data.target_customer.lower()
        combined_text = f"{brand} {competitors} {target}"

        for category, words in self._keywords.items():
            for word in words:
                if word in combined_text:
                    return category

        return "general"
