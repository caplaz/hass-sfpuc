"""Tests for San Francisco Water Power Sewer coordinator."""

from datetime import timedelta
from unittest.mock import Mock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.sfpuc.const import DEFAULT_UPDATE_INTERVAL
from custom_components.sfpuc.coordinator import SFWaterCoordinator

from .common import MockConfigEntry


class TestSFWaterCoordinator:
    """Test the San Francisco Water Power Sewer coordinator functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self, hass):
        """Set up test fixtures."""
        self.hass = hass
        self.config_entry = MockConfigEntry()
        # Add recorder instance to hass.data for statistics insertion
        from homeassistant.components.recorder.util import DATA_INSTANCE

        if DATA_INSTANCE not in hass.data:
            hass.data[DATA_INSTANCE] = Mock()

    def test_coordinator_initialization(self, hass, config_entry):
        """Test coordinator initialization."""
        coordinator = SFWaterCoordinator(hass, config_entry)

        assert coordinator.config_entry == config_entry
        assert coordinator._last_backfill_date is None
        assert coordinator._historical_data_fetched is False
        assert coordinator.update_interval == timedelta(minutes=DEFAULT_UPDATE_INTERVAL)

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @pytest.mark.asyncio
    async def test_update_data_success_first_run(
        self, mock_scraper_class, hass, config_entry
    ):
        """Test successful data update on first run."""
        # Mock the scraper
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.login.return_value = True

        coordinator = SFWaterCoordinator(hass, config_entry)

        # Mock statistics_during_period and async_add_external_statistics
        from unittest.mock import AsyncMock

        safe_account = (
            config_entry.data.get("username", "unknown").replace("-", "_").lower()
        )
        stat_id = f"sfpuc:{safe_account}_water_consumption"

        with (
            patch(
                "homeassistant.components.recorder.get_instance"
            ) as mock_get_instance,
            patch(
                "custom_components.sfpuc.statistics_handler.async_add_external_statistics"
            ),
            patch.object(
                coordinator, "_async_backfill_missing_data", return_value=None
            ),
            patch.object(
                coordinator, "_async_check_has_historical_data", return_value=False
            ),
            patch.object(coordinator, "_async_detect_billing_day", return_value=None),
        ):
            mock_recorder = Mock()
            mock_recorder.async_add_executor_job = AsyncMock(
                return_value={stat_id: [{"state": 95.0}, {"state": 45.0}]}
            )
            mock_get_instance.return_value = mock_recorder
            result = await coordinator._async_update_data()

        assert result["current_bill_usage"] == 140.0  # Sum of the states
        assert "last_updated" in result
        assert (
            coordinator._historical_data_fetched is False
        )  # Background task scheduled, not completed

        # No direct calls to get_usage_data in _async_update_data (backfill mocked)
        assert mock_scraper.get_usage_data.call_count == 0

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @pytest.mark.asyncio
    async def test_update_data_login_failure(
        self, mock_scraper_class, hass, config_entry
    ):
        """Test data update with login failure."""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.login.return_value = False

        coordinator = SFWaterCoordinator(hass, config_entry)

        with pytest.raises(UpdateFailed, match="Failed to login to SF PUC"):
            await coordinator._async_update_data()

    @patch("custom_components.sfpuc.coordinator.SFPUCScraper")
    @pytest.mark.asyncio
    async def test_update_data_no_current_data(
        self, mock_scraper_class, hass, config_entry
    ):
        """Test data update when no current data is available."""
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.login.return_value = True
        mock_scraper.get_usage_data.return_value = None

        coordinator = SFWaterCoordinator(hass, config_entry)

        # Mock statistics to return empty
        from unittest.mock import AsyncMock

        with (
            patch(
                "homeassistant.components.recorder.get_instance"
            ) as mock_get_instance,
            patch(
                "custom_components.sfpuc.statistics_handler.async_add_external_statistics"
            ),
            patch.object(
                coordinator, "_async_backfill_missing_data", return_value=None
            ),
            patch.object(
                coordinator, "_async_check_has_historical_data", return_value=False
            ),
            patch.object(coordinator, "_async_detect_billing_day", return_value=None),
        ):
            mock_recorder = Mock()
            mock_recorder.async_add_executor_job = AsyncMock(
                return_value={}
            )  # Empty stats
            mock_get_instance.return_value = mock_recorder
            result = await coordinator._async_update_data()

        assert result["current_bill_usage"] == 0.0
        assert "last_updated" in result
