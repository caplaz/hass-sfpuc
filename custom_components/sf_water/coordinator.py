"""Coordinator for SF Water integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
import requests

from .const import CONF_PASSWORD, CONF_USERNAME, DEFAULT_UPDATE_INTERVAL, DOMAIN


class SFPUCScraper:
    """SF PUC water usage data scraper."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the scraper."""
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = "https://myaccount-water.sfpuc.org"

        # Mimic a real browser
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def login(self) -> bool:
        """Login to SFPUC account."""
        try:
            # GET the login page to extract ViewState
            login_url = f"{self.base_url}/"
            response = self.session.get(login_url)
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract hidden form fields
            viewstate = soup.find("input", {"name": "__VIEWSTATE"})
            eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})
            viewstate_generator = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})

            if not viewstate or not eventvalidation:
                return False

            # Login form data
            login_data = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": viewstate["value"],
                "__VIEWSTATEGENERATOR": (
                    viewstate_generator["value"] if viewstate_generator else ""
                ),
                "__SCROLLPOSITIONX": "0",
                "__SCROLLPOSITIONY": "0",
                "__EVENTVALIDATION": eventvalidation["value"],
                "tb_USER_ID": self.username,
                "tb_USER_PSWD": self.password,
                "cb_REMEMBER_ME": "on",
                "btn_SIGN_IN_BUTTON": "Sign+in",
            }

            # Submit login
            response = self.session.post(
                login_url, data=login_data, allow_redirects=True
            )

            # Check if login successful
            if "MY_ACCOUNT_RSF.aspx" in response.url or "Welcome" in response.text:
                return True
            else:
                return False

        except Exception:
            return False

    def get_usage_data(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
        resolution: str = "hourly",
    ) -> list[dict[str, Any]] | None:
        """Get water usage data for the specified date range and resolution.

        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval (defaults to start_date)
            resolution: Data resolution - "hourly", "daily", or "monthly"

        Returns:
            List of usage data points with timestamps and values
        """
        if end_date is None:
            end_date = start_date

        try:
            # Navigate to appropriate usage page based on resolution
            if resolution == "hourly":
                usage_url = f"{self.base_url}/USE_HOURLY.aspx"
                data_type = "Hourly+Use"
            elif resolution == "daily":
                usage_url = f"{self.base_url}/USE_DAILY.aspx"
                data_type = "Daily+Use"
            elif resolution == "monthly":
                usage_url = f"{self.base_url}/USE_MONTHLY.aspx"
                data_type = "Monthly+Use"
            else:
                return None

            response = self.session.get(usage_url)
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract form tokens
            tokens = {}
            form = soup.find("form")
            if form:
                for inp in form.find_all("input"):
                    name = inp.get("name")
                    if name:
                        tokens[name] = inp.get("value", "")

            # Set download parameters
            tokens.update(
                {
                    "img_EXCEL_DOWNLOAD_IMAGE.x": "8",
                    "img_EXCEL_DOWNLOAD_IMAGE.y": "13",
                    "tb_DAILY_USE": data_type,
                    "SD": start_date.strftime("%m/%d/%Y"),
                    "ED": end_date.strftime("%m/%d/%Y"),
                    "dl_UOM": "GALLONS",
                }
            )

            # POST to trigger download
            download_url = f"{self.base_url}/USE_{resolution.upper()}.aspx"
            response = self.session.post(
                download_url, data=tokens, allow_redirects=True
            )

            if "TRANSACTIONS_EXCEL_DOWNLOAD.aspx" in response.url:
                # Parse the Excel data
                content = response.content.decode("utf-8", errors="ignore")
                lines = content.split("\n")

                usage_data = []
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            try:
                                # Parse timestamp and usage
                                timestamp_str = parts[0].strip()
                                usage = float(parts[1])

                                # Parse timestamp based on resolution
                                if resolution == "hourly":
                                    # Format: MM/DD/YYYY HH:MM:SS
                                    timestamp = datetime.strptime(
                                        timestamp_str, "%m/%d/%Y %H:%M:%S"
                                    )
                                elif resolution == "daily":
                                    # Format: MM/DD/YYYY
                                    timestamp = datetime.strptime(
                                        timestamp_str, "%m/%d/%Y"
                                    )
                                elif resolution == "monthly":
                                    # Format: MM/YYYY
                                    timestamp = datetime.strptime(
                                        timestamp_str, "%m/%Y"
                                    )

                                usage_data.append(
                                    {
                                        "timestamp": timestamp,
                                        "usage": usage,
                                        "resolution": resolution,
                                    }
                                )
                            except (ValueError, IndexError):
                                continue

                return usage_data
            else:
                return None

        except Exception:
            return None

    def get_daily_usage(self) -> float | None:
        """Get today's water usage in gallons (legacy method for backward compatibility)."""
        today = datetime.now()
        data = self.get_usage_data(today, today, "hourly")
        if data:
            # Sum all hourly usage for the day
            return sum(item["usage"] for item in data)
        return None


class SFWaterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """SF Water data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry[Any],
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=hass.data[DOMAIN]["logger"],
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )
        self.config_entry = config_entry
        self.scraper = SFPUCScraper(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
        )
        self._last_backfill_date: datetime | None = None
        self._historical_data_fetched = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from SF PUC."""
        try:
            # Login (run in executor since it's blocking)
            loop = asyncio.get_event_loop()
            login_success = await loop.run_in_executor(None, self.scraper.login)

            if not login_success:
                raise UpdateFailed("Failed to login to SF PUC")

            # Fetch historical data on first run
            if not self._historical_data_fetched:
                await self._async_fetch_historical_data()
                self._historical_data_fetched = True

            # Perform backfilling if needed (30-day lookback)
            await self._async_backfill_missing_data()

            # Get current daily usage
            today = datetime.now()
            daily_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, today, today, "hourly"
            )

            if not daily_data:
                raise UpdateFailed("Failed to retrieve current usage data")

            # Sum hourly data for daily total
            daily_usage = sum(item["usage"] for item in daily_data)

            # Get latest hourly usage (most recent hour)
            hourly_usage = daily_data[-1]["usage"] if daily_data else 0

            # Get current monthly usage (sum of daily data this month)
            start_of_month = today.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            monthly_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, start_of_month, today, "daily"
            )
            monthly_usage = (
                sum(item["usage"] for item in monthly_data) if monthly_data else 0
            )

            data = {
                "daily_usage": daily_usage,
                "hourly_usage": hourly_usage,
                "monthly_usage": monthly_usage,
                "last_updated": datetime.now(),
            }

            # Insert current statistics
            await self._async_insert_statistics(daily_data)

            return data

        except Exception as err:
            raise UpdateFailed(f"Error updating SF Water data: {err}") from err

    async def _async_fetch_historical_data(self) -> None:
        """Fetch historical data going back months/years on first run."""
        try:
            self.logger.info("Fetching historical water usage data...")

            # Fetch data at different resolutions
            # Start with monthly data for the past 2 years
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # 2 years

            loop = asyncio.get_event_loop()

            # Fetch monthly data
            monthly_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, start_date, end_date, "monthly"
            )
            if monthly_data:
                await self._async_insert_statistics(monthly_data)
                self.logger.info("Fetched %d monthly data points", len(monthly_data))

            # Fetch daily data for the past 90 days (more detailed recent data)
            start_date = end_date - timedelta(days=90)
            daily_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, start_date, end_date, "daily"
            )
            if daily_data:
                await self._async_insert_statistics(daily_data)
                self.logger.info("Fetched %d daily data points", len(daily_data))

            # Fetch hourly data for the past 30 days (most detailed recent data)
            start_date = end_date - timedelta(days=30)
            hourly_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, start_date, end_date, "hourly"
            )
            if hourly_data:
                await self._async_insert_statistics(hourly_data)
                self.logger.info("Fetched %d hourly data points", len(hourly_data))

        except Exception as err:
            self.logger.warning("Failed to fetch historical data: %s", err)

    async def _async_backfill_missing_data(self) -> None:
        """Backfill missing data with 30-day lookback window."""
        try:
            now = datetime.now()

            # Check if we need to backfill (run this less frequently)
            if self._last_backfill_date and (
                now - self._last_backfill_date
            ) < timedelta(hours=24):
                return

            self.logger.debug("Checking for missing data to backfill...")

            # Look back 30 days for any missing data
            lookback_date = now - timedelta(days=30)

            loop = asyncio.get_event_loop()

            # Check for missing daily data in the lookback period
            daily_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, lookback_date, now, "daily"
            )
            if daily_data:
                await self._async_insert_statistics(daily_data)
                self.logger.debug("Backfilled %d daily data points", len(daily_data))

            # Check for missing hourly data in the recent past (last 7 days)
            recent_start = now - timedelta(days=7)
            hourly_data = await loop.run_in_executor(
                None, self.scraper.get_usage_data, recent_start, now, "hourly"
            )
            if hourly_data:
                await self._async_insert_statistics(hourly_data)
                self.logger.debug("Backfilled %d hourly data points", len(hourly_data))

            self._last_backfill_date = now

        except Exception as err:
            self.logger.warning("Failed to backfill missing data: %s", err)

    async def _async_insert_statistics(
        self, usage_data: float | list[dict[str, Any]]
    ) -> None:
        """Insert water usage statistics into Home Assistant."""
        try:
            if isinstance(usage_data, (int, float)):
                # Legacy format: single daily usage value
                await self._async_insert_legacy_statistics(usage_data)
                return

            # New format: list of data points
            if not usage_data:
                return

            # Group data by resolution
            hourly_data = []
            daily_data = []
            monthly_data = []

            for item in usage_data:
                resolution = item.get("resolution", "daily")
                if resolution == "hourly":
                    hourly_data.append(item)
                elif resolution == "daily":
                    daily_data.append(item)
                elif resolution == "monthly":
                    monthly_data.append(item)

            # Insert statistics for each resolution
            if hourly_data:
                await self._async_insert_resolution_statistics(hourly_data, "hourly")
            if daily_data:
                await self._async_insert_resolution_statistics(daily_data, "daily")
            if monthly_data:
                await self._async_insert_resolution_statistics(monthly_data, "monthly")

        except Exception as err:
            self.logger.warning("Failed to insert water usage statistics: %s", err)

    async def _async_insert_resolution_statistics(
        self, data_points: list[dict[str, Any]], resolution: str
    ) -> None:
        """Insert statistics for a specific resolution."""
        try:
            # Create statistic metadata based on resolution
            if resolution == "hourly":
                stat_id = f"{DOMAIN}:hourly_usage"
                name = "SF Water Hourly Usage"
                has_sum = True
                unit_class = "volume"
            elif resolution == "daily":
                stat_id = f"{DOMAIN}:daily_usage"
                name = "SF Water Daily Usage"
                has_sum = True
                unit_class = "volume"
            elif resolution == "monthly":
                stat_id = f"{DOMAIN}:monthly_usage"
                name = "SF Water Monthly Usage"
                has_sum = True
                unit_class = "volume"
            else:
                return

            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=has_sum,
                mean_type=StatisticMeanType.NONE,
                name=name,
                source=DOMAIN,
                statistic_id=stat_id,
                unit_class=unit_class,
                unit_of_measurement=UnitOfVolume.GALLONS,
            )

            # Create statistic data points
            statistic_data = []
            for point in data_points:
                timestamp = point["timestamp"]
                usage = point["usage"]

                # Adjust timestamp based on resolution
                if resolution == "hourly":
                    start_time = timestamp
                elif resolution == "daily":
                    start_time = timestamp.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                elif resolution == "monthly":
                    start_time = timestamp.replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )

                statistic_data.append(
                    StatisticData(
                        start=start_time,
                        state=usage,
                        sum=usage,
                    )
                )

            # Insert statistics into Home Assistant recorder
            async_add_external_statistics(self.hass, metadata, statistic_data)

        except Exception as err:
            self.logger.warning("Failed to insert %s statistics: %s", resolution, err)

    async def _async_insert_legacy_statistics(self, daily_usage: float) -> None:
        """Insert legacy daily statistics (backward compatibility)."""
        try:
            # Create statistic metadata for daily water usage
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name="SF Water Daily Usage",
                source=DOMAIN,
                statistic_id=f"{DOMAIN}:daily_usage",
                unit_class="volume",
                unit_of_measurement=UnitOfVolume.GALLONS,
            )

            # Get current date for the statistic
            now = dt_util.now()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Create statistic data point
            statistic_data = [
                StatisticData(
                    start=start_of_day,
                    state=daily_usage,
                    sum=daily_usage,
                )
            ]

            # Insert statistics into Home Assistant recorder
            async_add_external_statistics(self.hass, metadata, statistic_data)

        except Exception as err:
            self.logger.warning(
                "Failed to insert legacy water usage statistics: %s", err
            )
