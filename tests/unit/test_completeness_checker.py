"""Unit tests for the source CompletenessChecker.

Exercises src/brief_scout/domain/services/completeness_checker.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brief_scout.domain.models.intake import IntakeData
from brief_scout.domain.services.completeness_checker import (
    CompletenessChecker,
    CompletenessResult,
)
from brief_scout.infrastructure.config.journey_loader import JourneyLoader
from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)


@pytest.fixture
def telemetry(tmp_path: Path) -> LocalFileTelemetryAdapter:
    """Provide a LocalFileTelemetryAdapter writing to a temp directory."""
    return LocalFileTelemetryAdapter(log_dir=str(tmp_path / "logs"))


@pytest.fixture
def checker(telemetry: LocalFileTelemetryAdapter) -> CompletenessChecker:
    """Provide a CompletenessChecker with a telemetry adapter."""
    journey = JourneyLoader(config_dir="config", env="development").load()
    return CompletenessChecker(journey=journey, telemetry=telemetry)


class TestCompletenessChecker:
    """Tests for intake data completeness evaluation."""

    def test_should_report_complete_when_all_fields_present(
        self, checker: CompletenessChecker
    ) -> None:
        """All required fields present → is_complete True."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            competitors=["Adidas", "Puma"],
            primary_goal="acquisition",
            target_customer="athletes",
        )
        result = checker.check(data)

        assert isinstance(result, CompletenessResult)
        assert result.is_complete is True
        assert result.ready_to_research is True
        assert result.missing_fields == []
        assert result.confidence == data.completion_score

    def test_should_report_missing_first_name(self, checker: CompletenessChecker) -> None:
        """Missing first_name should be reported."""
        data = IntakeData(
            brand_name="Nike",
            competitors=["Adidas"],
            primary_goal="acquisition",
            target_customer="athletes",
        )
        result = checker.check(data)

        assert result.is_complete is False
        assert "first_name" in result.missing_fields

    def test_should_report_missing_brand_name(self, checker: CompletenessChecker) -> None:
        """Missing brand_name should be reported."""
        data = IntakeData(
            first_name="Alex",
            competitors=["Adidas"],
            primary_goal="acquisition",
            target_customer="athletes",
        )
        result = checker.check(data)

        assert result.is_complete is False
        assert "brand_name" in result.missing_fields

    def test_should_report_missing_competitors(self, checker: CompletenessChecker) -> None:
        """Empty competitors list should be reported."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            primary_goal="acquisition",
            target_customer="athletes",
        )
        result = checker.check(data)

        assert result.is_complete is False
        assert "competitors" in result.missing_fields

    def test_should_report_missing_primary_goal(self, checker: CompletenessChecker) -> None:
        """Missing primary_goal should be reported."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            competitors=["Adidas"],
            target_customer="athletes",
        )
        result = checker.check(data)

        assert result.is_complete is False
        assert "primary_goal" in result.missing_fields

    def test_should_report_missing_target_customer(self, checker: CompletenessChecker) -> None:
        """Missing target_customer should be reported."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            competitors=["Adidas"],
            primary_goal="acquisition",
        )
        result = checker.check(data)

        assert result.is_complete is False
        assert "target_customer" in result.missing_fields

    def test_should_report_all_missing_fields(self, checker: CompletenessChecker) -> None:
        """Empty data should report all required fields missing."""
        data = IntakeData()
        result = checker.check(data)

        assert result.is_complete is False
        assert set(result.missing_fields) == {
            "first_name",
            "brand_name",
            "competitors",
            "primary_goal",
            "target_customer",
        }

    def test_required_fields_match_journey(self, checker: CompletenessChecker) -> None:
        """Required fields should be derived from the journey schema."""
        journey = JourneyLoader(config_dir="config", env="development").load()
        expected = [f.name for f in journey.required_fields]
        result = checker.check(IntakeData())
        assert set(result.missing_fields) == set(expected)
