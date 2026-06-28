"""Unit tests for CategoryClassifier."""

from __future__ import annotations

from brief_scout.domain.models.intake import IntakeData
from brief_scout.domain.services.category_classifier import (
    DEFAULT_KEYWORDS,
    CategoryClassifier,
)


class TestCategoryClassifier:
    """Tests for keyword-based category inference."""

    def test_classify_technology(self) -> None:
        """Software keywords should map to technology/software."""
        classifier = CategoryClassifier()
        intake = IntakeData(
            brand_name="SaaS Co",
            target_customer="software buyers",
        )
        assert classifier.classify(intake) == "technology / software"

    def test_classify_apparel(self) -> None:
        """Apparel keywords should map to apparel/footwear."""
        classifier = CategoryClassifier()
        intake = IntakeData(
            brand_name="SneakerHub",
            target_customer="sneaker enthusiasts",
        )
        assert classifier.classify(intake) == "apparel / footwear"

    def test_classify_general_by_default(self) -> None:
        """No keyword match should return 'general'."""
        classifier = CategoryClassifier()
        intake = IntakeData(brand_name="Xyz", target_customer="everyone")
        assert classifier.classify(intake) == "general"

    def test_custom_keywords(self) -> None:
        """A custom keyword map should be respected."""
        classifier = CategoryClassifier({"space": ["rocket", "orbit"]})
        intake = IntakeData(brand_name="OrbitX", target_customer="rocket fans")
        assert classifier.classify(intake) == "space"

    def test_default_keywords_are_nonempty(self) -> None:
        """The default keyword map should contain categories."""
        assert "technology / software" in DEFAULT_KEYWORDS
        assert DEFAULT_KEYWORDS["technology / software"]
