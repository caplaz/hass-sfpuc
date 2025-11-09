"""SF Water integration for Home Assistant.

This integration connects to SFPUC (San Francisco Public Utilities Commission)
to monitor water usage data from your account.

The integration provides:
- Sensor entity with daily water usage in gallons
- Historical data storage in Home Assistant database
- Automatic data fetching from SFPUC portal
- Support for multiple languages (English, Spanish)

Author: caplaz
License: MIT
"""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SF Water from a config entry.

    This function initializes the integration by:
    1. Creating a data coordinator for managing water usage updates
    2. Setting up the sensor platform
    3. Registering update listeners for configuration changes

    Args:
        hass: Home Assistant instance
        entry: Configuration entry containing user credentials

    Returns:
        bool: True if setup was successful, False otherwise
    """
    _LOGGER.info("Setting up SF Water integration")

    # Create coordinator for managing updates
    coordinator = SFWaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options update listener for immediate refresh
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options and force immediate refresh.

    Called when user modifies integration configuration. Forces an immediate
    data refresh to apply new settings.

    Args:
        hass: Home Assistant instance
        entry: Updated configuration entry
    """
    _LOGGER.info("SF Water config updated, refreshing data immediately")

    # Get the coordinator and force an immediate refresh
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Cleanly removes the integration by unloading all platforms and
    removing stored data from Home Assistant.

    Args:
        hass: Home Assistant instance
        entry: Configuration entry to unload

    Returns:
        bool: True if unload was successful
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SFWaterCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SF Water usage data.

    This coordinator handles periodic updates of water usage data by:
    1. Connecting to SFPUC portal with user credentials
    2. Downloading and parsing water usage Excel files
    3. Providing consolidated water usage information to the sensor platform

    The coordinator respects user-configured update intervals and handles
    errors gracefully to maintain integration stability.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the water data coordinator.

        Args:
            hass: Home Assistant instance
            entry: Configuration entry with user credentials and settings
        """
        self.entry = entry
        update_interval = timedelta(minutes=entry.options.get("update_interval", 60))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update water usage data from SFPUC.

        Fetches current water usage data from SFPUC portal and processes it
        to provide daily usage information.

        Returns:
            dict: Water usage data including daily consumption in gallons

        Raises:
            UpdateFailed: If unable to connect to SFPUC or parse data
        """
        try:
            from .sensor import SFPUCScraper

            username = self.entry.data["username"]
            password = self.entry.data["password"]

            scraper = SFPUCScraper(username, password)
            if not scraper.login():
                raise UpdateFailed("Failed to authenticate with SFPUC")

            usage_data = scraper.get_usage_data()
            return {"daily_usage": usage_data}
        except Exception as err:
            _LOGGER.error("Error updating water usage data: %s", err)
            raise UpdateFailed(f"Failed to update water usage data: {err}") from err
