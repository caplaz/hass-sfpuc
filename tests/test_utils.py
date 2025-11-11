"""Tests for SFPUC utility functions."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from custom_components.sfpuc.coordinator import SFWaterCoordinator
from custom_components.sfpuc.utils import (
    async_detect_billing_day,
    calculate_billing_period,
)

from .common import MockConfigEntry


class TestUtils:
    """Test the SFPUC utility functions."""

    @pytest.fixture(autouse=True)
    def setup_method(self, hass):
        """Set up test fixtures."""
        self.hass = hass
        self.config_entry = MockConfigEntry()

    def test_calculate_billing_period_default_billing_day(self, hass, config_entry):
        """Test calculating billing period with default billing day (25th)."""
        coordinator = SFWaterCoordinator(hass, config_entry)
        # Billing day not set, should default to 25

        # Test case: Today is before billing day in current month
        # Mock datetime.now() to return a date before the 25th
        with patch("custom_components.sfpuc.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 10, 15)  # 15th
            start_date, end_date = calculate_billing_period(coordinator)

        expected_start = datetime(2023, 9, 25)  # Previous month billing day
        expected_end = datetime(2023, 10, 25)  # Current month billing day
        assert start_date == expected_start
        assert end_date == expected_end

    def test_calculate_billing_period_after_billing_day(self, hass, config_entry):
        """Test calculating billing period when past the billing day."""
        coordinator = SFWaterCoordinator(hass, config_entry)

        # Test case: Today is after billing day in current month
        with patch("custom_components.sfpuc.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 10, 30)  # 30th
            start_date, end_date = calculate_billing_period(coordinator)

        expected_start = datetime(2023, 10, 25)  # Current month billing day
        expected_end = datetime(2023, 11, 25)  # Next month billing day
        assert start_date == expected_start
        assert end_date == expected_end

    def test_calculate_billing_period_custom_billing_day(self, hass, config_entry):
        """Test calculating billing period with custom billing day."""
        coordinator = SFWaterCoordinator(hass, config_entry)
        coordinator._billing_day = 15  # Custom billing day

        with patch("custom_components.sfpuc.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2023, 10, 10
            )  # Before billing day
            start_date, end_date = calculate_billing_period(coordinator)

        expected_start = datetime(2023, 9, 15)  # Previous month billing day
        expected_end = datetime(2023, 10, 15)  # Current month billing day
        assert start_date == expected_start
        assert end_date == expected_end

    @pytest.mark.asyncio
    async def test_detect_billing_day_already_set(self, hass, config_entry):
        """Test detecting billing day when already set."""
        coordinator = SFWaterCoordinator(hass, config_entry)
        coordinator._billing_day = 15

        result = await async_detect_billing_day(coordinator)
        assert result == 15

    @pytest.mark.asyncio
    async def test_detect_billing_day_from_statistics(self, hass, config_entry):
        """Test detecting billing day from monthly statistics."""
        coordinator = SFWaterCoordinator(hass, config_entry)

        # Mock statistics data with billing days on the 25th
        mock_stats = {
            "sfpuc:test_example_com_water_consumption": [
                {"start": datetime(2023, 8, 25)},
                {"start": datetime(2023, 9, 25)},
                {"start": datetime(2023, 10, 25)},
            ]
        }

        with (
            patch("custom_components.sfpuc.utils.get_instance") as mock_get_instance,
            patch(
                "custom_components.sfpuc.utils.statistics_during_period"
            ) as mock_stats_during_period,
        ):
            mock_recorder = Mock()
            mock_recorder.async_add_executor_job = Mock(return_value=mock_stats)
            mock_get_instance.return_value = mock_recorder
            mock_stats_during_period.return_value = mock_stats

            result = await async_detect_billing_day(coordinator)

        assert result == 25
        assert coordinator._billing_day == 25

    @pytest.mark.asyncio
    async def test_detect_billing_day_no_statistics(self, hass, config_entry):
        """Test detecting billing day when no statistics available."""
        coordinator = SFWaterCoordinator(hass, config_entry)

        with patch("custom_components.sfpuc.utils.get_instance") as mock_get_instance:
            mock_recorder = Mock()
            mock_recorder.async_add_executor_job = Mock(return_value={})
            mock_get_instance.return_value = mock_recorder

            result = await async_detect_billing_day(coordinator)

        assert result == 25  # Default fallback
        assert coordinator._billing_day == 25

    @pytest.mark.asyncio
    async def test_detect_billing_day_exception(self, hass, config_entry):
        """Test detecting billing day when exception occurs."""
        coordinator = SFWaterCoordinator(hass, config_entry)

        with patch("custom_components.sfpuc.utils.get_instance") as mock_get_instance:
            mock_recorder = Mock()
            mock_recorder.async_add_executor_job = Mock(
                side_effect=Exception("Database error")
            )
            mock_get_instance.return_value = mock_recorder

            result = await async_detect_billing_day(coordinator)

        assert result == 25  # Default fallback
        assert coordinator._billing_day == 25
