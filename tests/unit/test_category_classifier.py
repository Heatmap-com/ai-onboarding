"""Unit tests for CategoryClassifier."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from brief_scout.domain.models.intake import IntakeData
from brief_scout.domain.services.category_classifier import (
    DEFAULT_KEYWORDS,
    CategoryClassifier,
)


class TestCategoryClassifier:
    """Tests for category inference."""

    @pytest.mark.asyncio
    async def test_classify_technology(self) -> None:
        """Software keywords should map to technology/software."""
        classifier = CategoryClassifier()
        intake = IntakeData(
            brand_name="SaaS Co",
            target_customer="software buyers",
        )
        assert await classifier.classify(intake) == "technology / software"

    @pytest.mark.asyncio
    async def test_classify_apparel(self) -> None:
        """Apparel keywords should map to apparel/footwear."""
        classifier = CategoryClassifier()
        intake = IntakeData(
            brand_name="SneakerHub",
            target_customer="sneaker enthusiasts",
        )
        assert await classifier.classify(intake) == "apparel / footwear"

    @pytest.mark.asyncio
    async def test_classify_general_by_default(self) -> None:
        """No keyword match should return 'general'."""
        classifier = CategoryClassifier()
        intake = IntakeData(brand_name="Xyz", target_customer="everyone")
        assert await classifier.classify(intake) == "general"

    @pytest.mark.asyncio
    async def test_custom_keywords(self) -> None:
        """A custom keyword map should be respected."""
        classifier = CategoryClassifier(keywords={"space": ["rocket", "orbit"]})
        intake = IntakeData(brand_name="OrbitX", target_customer="rocket fans")
        assert await classifier.classify(intake) == "space"

    @pytest.mark.asyncio
    async def test_llm_classifier_used_when_available(self) -> None:
        """When an LLM port is provided, its structured result is preferred."""
        llm = AsyncMock()
        llm.complete_structured.return_value.category = "food & beverage"
        classifier = CategoryClassifier(llm=llm)
        intake = IntakeData(brand_name="SaaS Co", target_customer="software buyers")
        result = await classifier.classify(intake)
        assert result == "food & beverage"
        llm.complete_structured.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_classifier_falls_back_on_invalid_category(self) -> None:
        """Invalid LLM categories fall back to keyword classification."""
        llm = AsyncMock()
        llm.complete_structured.return_value.category = "unknown category"
        classifier = CategoryClassifier(llm=llm)
        intake = IntakeData(brand_name="SneakerHub", target_customer="sneaker enthusiasts")
        result = await classifier.classify(intake)
        assert result == "apparel / footwear"

    def test_default_keywords_are_nonempty(self) -> None:
        """The default keyword map should contain categories."""
        assert "technology / software" in DEFAULT_KEYWORDS
        assert DEFAULT_KEYWORDS["technology / software"]
