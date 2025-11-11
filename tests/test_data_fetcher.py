"""Tests for SFPUC data fetching operations."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from custom_components.sfpuc.coordinator import SFWaterCoordinator
from custom_components.sfpuc.data_fetcher import (
    async_backfill_missing_data,
    async_fetch_historical_data,
)

from .common import MockConfigEntry


class TestDataFetcher:
    """Test the SFPUC data fetching functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self, hass):
        """Set up test fixtures."""
        self.hass = hass
        self.config_entry = MockConfigEntry()
        # Add recorder instance to hass.data for statistics insertion
        from homeassistant.components.recorder.util import DATA_INSTANCE

        if DATA_INSTANCE not in hass.data:
            hass.data[DATA_INSTANCE] = Mock()

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @pytest.mark.asyncio
    async def test_fetch_historical_data_success(
        self, mock_scraper_class, hass, config_entry
    ):
        """Test successful historical data fetching."""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.get_usage_data.side_effect = [
            # Monthly data
            [
                {
                    "timestamp": datetime(2023, 9, 15),
                    "usage": 150.0,
                    "resolution": "monthly",
                }
            ],
            # Daily data chunks
            [
                {
                    "timestamp": datetime(2023, 9, 15),
                    "usage": 150.0,
                    "resolution": "daily",
                }
            ],
            [],  # Empty chunk
            # Hourly data
            [
                {
                    "timestamp": datetime(2023, 9, 30, 15, 0),
                    "usage": 25.0,
                    "resolution": "hourly",
                }
            ],
        ]

        coordinator = SFWaterCoordinator(hass, config_entry)

        with patch(
            "custom_components.sfpuc.statistics_handler.async_add_external_statistics"
        ) as mock_add_stats:
            await async_fetch_historical_data(coordinator)

        # Verify historical data calls were made
        assert (
            mock_scraper.get_usage_data.call_count >= 3
        )  # At least monthly, daily, and hourly calls

        # Verify statistics were added
        assert mock_add_stats.call_count >= 1

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @patch("custom_components.sfpuc.coordinator._LOGGER")
    @pytest.mark.asyncio
    async def test_fetch_historical_data_failure(
        self, mock_logger, mock_scraper_class, hass, config_entry
    ):
        """Test historical data fetching with failures."""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.get_usage_data.side_effect = Exception("Network error")

        coordinator = SFWaterCoordinator(hass, config_entry)

        # Should not raise exception, just log warning
        await async_fetch_historical_data(coordinator)

        # Verify logger was called
        mock_logger.warning.assert_called()

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @pytest.mark.asyncio
    async def test_backfill_missing_data_first_run(
        self, mock_scraper_class, hass, config_entry
    ):
        """Test backfilling on first run."""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.get_usage_data.side_effect = [
            # Daily backfill data
            [
                {
                    "timestamp": datetime(2023, 9, 25),
                    "usage": 140.0,
                    "resolution": "daily",
                }
            ],
            # Hourly backfill data
            [
                {
                    "timestamp": datetime(2023, 9, 28, 10, 0),
                    "usage": 20.0,
                    "resolution": "hourly",
                }
            ],
        ]

        coordinator = SFWaterCoordinator(hass, config_entry)

        with patch(
            "custom_components.sfpuc.statistics_handler.async_add_external_statistics"
        ) as mock_add_stats:
            await async_backfill_missing_data(coordinator)

        # Should perform backfill on first run
        assert mock_scraper.get_usage_data.call_count == 3
        assert mock_add_stats.call_count == 1
        assert coordinator._last_backfill_date is not None

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @pytest.mark.asyncio
    async def test_backfill_missing_data_recent_run(
        self, mock_scraper_class, hass, config_entry
    ):
        """Test backfilling is skipped when recently run."""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper

        coordinator = SFWaterCoordinator(hass, config_entry)
        # Set last backfill to recent time
        coordinator._last_backfill_date = datetime.now() - timedelta(hours=1)

        await async_backfill_missing_data(coordinator)

        # Should not perform backfill
        mock_scraper.get_usage_data.assert_not_called()
