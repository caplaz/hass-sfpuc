"""Sensor entities for SF Water integration."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_PASSWORD, CONF_UPDATE_INTERVAL, CONF_USERNAME, DOMAIN, KEY_DAILY_USAGE, SENSOR_TYPES
from .version import __version__

_LOGGER = logging.getLogger(__name__)


class SFPUCScraper:
    """SF PUC water usage data scraper."""

    def __init__(self, username: str, password: str):
        """Initialize the scraper."""
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = "https://myaccount-water.sfpuc.org"

        # Mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def login(self) -> bool:
        """Login to SFPUC account."""
        try:
            # GET the login page to extract ViewState
            login_url = f"{self.base_url}/"
            response = self.session.get(login_url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract hidden form fields
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
            viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})

            if not viewstate or not eventvalidation:
                _LOGGER.error("Could not find ViewState tokens on login page")
                return False

            # Login form data
            login_data = {
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': viewstate['value'],
                '__VIEWSTATEGENERATOR': viewstate_generator['value'] if viewstate_generator else '',
                '__SCROLLPOSITIONX': '0',
                '__SCROLLPOSITIONY': '0',
                '__EVENTVALIDATION': eventvalidation['value'],
                'tb_USER_ID': self.username,
                'tb_USER_PSWD': self.password,
                'cb_REMEMBER_ME': 'on',
                'btn_SIGN_IN_BUTTON': 'Sign+in'
            }

            # Submit login
            response = self.session.post(login_url, data=login_data, allow_redirects=True)

            # Check if login successful
            if 'MY_ACCOUNT_RSF.aspx' in response.url or 'Welcome' in response.text:
                _LOGGER.info("Login successful")
                return True
            else:
                _LOGGER.error("Login failed - check credentials")
                return False

        except Exception as e:
            _LOGGER.error("Login error: %s", e)
            return False

    def get_daily_usage(self) -> float | None:
        """Get today's water usage in gallons."""
        try:
            # Navigate to hourly usage page
            usage_url = f"{self.base_url}/USE_HOURLY.aspx"
            response = self.session.get(usage_url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract form tokens
            tokens = {}
            form = soup.find('form')
            if form:
                for inp in form.find_all('input'):
                    name = inp.get('name')
                    if name:
                        tokens[name] = inp.get('value', '')

            # Set download parameters for today's usage
            today = datetime.now().strftime('%m/%d/%Y')
            tokens.update({
                'img_EXCEL_DOWNLOAD_IMAGE.x': '8',
                'img_EXCEL_DOWNLOAD_IMAGE.y': '13',
                'tb_DAILY_USE': 'Hourly+Use',
                'SD': today,
                'dl_UOM': 'GALLONS'
            })

            # POST to trigger download
            download_url = f"{self.base_url}/USE_HOURLY.aspx"
            response = self.session.post(download_url, data=tokens, allow_redirects=True)

            if 'TRANSACTIONS_EXCEL_DOWNLOAD.aspx' in response.url:
                # Parse the Excel data
                content = response.content.decode('utf-8', errors='ignore')
                lines = content.split('\n')

                total_usage = 0.0
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            try:
                                usage = float(parts[1])
                                total_usage += usage
                            except (ValueError, IndexError):
                                continue

                _LOGGER.info("Retrieved daily usage: %.2f gallons", total_usage)
                return total_usage
            else:
                _LOGGER.error("Failed to download usage data")
                return None

        except Exception as e:
            _LOGGER.error("Error retrieving usage data: %s", e)
            return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SF Water sensor entities."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    update_interval = config_entry.options.get(CONF_UPDATE_INTERVAL, 60)

    scraper = SFPUCScraper(username, password)

    async def async_update_data() -> Dict[str, Any]:
        """Fetch data from SF PUC."""
        try:
            # Login
            if not scraper.login():
                raise UpdateFailed("Failed to login to SF PUC")

            # Get daily usage
            daily_usage = scraper.get_daily_usage()
            if daily_usage is None:
                raise UpdateFailed("Failed to retrieve usage data")

            return {
                KEY_DAILY_USAGE: daily_usage,
                "last_updated": datetime.now(),
            }
        except Exception as e:
            _LOGGER.error("Error updating SF Water data: %s", e)
            raise UpdateFailed(f"Error updating data: {e}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="SF Water",
        update_method=async_update_data,
        update_interval=timedelta(minutes=update_interval),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(SFWaterSensor(coordinator, config_entry, sensor_type))

    async_add_entities(sensors)


class SFWaterSensor(CoordinatorEntity, SensorEntity):
    """SF Water sensor entity."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, config_entry, sensor_type):
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._sensor_config = SENSOR_TYPES[sensor_type]

        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_name = self._sensor_config["name"]
        self._attr_native_unit_of_measurement = self._sensor_config["unit"]
        self._attr_icon = self._sensor_config["icon"]

        # Set device class if available
        if "device_class" in self._sensor_config:
            self._attr_device_class = getattr(
                SensorDeviceClass, self._sensor_config["device_class"].upper(), None
            )

        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "SF Water",
            "manufacturer": "SF PUC",
            "model": "Water Usage Tracker",
            "sw_version": __version__,
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._sensor_type)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
