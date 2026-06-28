"""Category classifier for research prompts.

Infers a high-level product category from intake data using a keyword map.
The map is injectable so new categories can be added without editing the
classifier itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData


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


class CategoryClassifier:
    """Keyword-based category inference."""

    def __init__(self, keywords: dict[str, list[str]] | None = None) -> None:
        """Initialize with a keyword map.

        Args:
            keywords: Mapping from category name to lowercase keywords.
                Defaults to ``DEFAULT_KEYWORDS``.
        """
        self._keywords = keywords or DEFAULT_KEYWORDS

    def classify(self, intake_data: IntakeData) -> str:
        """Infer a category from intake data.

        Args:
            intake_data: Structured intake data.

        Returns:
            Inferred category string, or ``"general"`` when no keywords match.
        """
        brand = intake_data.brand_name.lower()
        competitors = " ".join(c.lower() for c in intake_data.competitors)
        target = intake_data.target_customer.lower()
        combined_text = f"{brand} {competitors} {target}"

        for category, words in self._keywords.items():
            for word in words:
                if word in combined_text:
                    return category

        return "general"
