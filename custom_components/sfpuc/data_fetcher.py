"""Data fetching utilities for SFPUC coordinator."""

import asyncio
from datetime import datetime, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.util import dt as dt_util

from .const import CONF_USERNAME, DOMAIN
from .statistics_handler import async_insert_statistics


async def async_check_has_historical_data(coordinator) -> bool:
    """Check if we already have sufficient historical data in the database.

    Returns True if we have daily statistics going back at least 1 year.
    This prevents re-fetching 2 years of data on every HA restart.
    """
    try:
        # Check for daily statistics from 1 year ago
        one_year_ago = datetime.now() - timedelta(days=365)
        safe_account = (
            coordinator.config_entry.data.get(CONF_USERNAME, "unknown")
            .replace("-", "_")
            .lower()
        )
        stat_id = f"{DOMAIN}:{safe_account}_water_consumption"

        stats = await get_instance(coordinator.hass).async_add_executor_job(
            statistics_during_period,
            coordinator.hass,
            dt_util.as_utc(one_year_ago),
            None,  # end_time (None = now)
            {stat_id},
            "hour",  # period
            None,  # units
            {"sum"},  # types
        )

        # If we have statistics going back at least 1 year, consider historical data fetched
        if stat_id in stats and len(stats[stat_id]) > 300:  # ~300 days minimum
            coordinator.logger.info(
                "Found %d existing daily statistics records - skipping historical data fetch",
                len(stats[stat_id]),
            )
            return True

        coordinator.logger.debug("No sufficient historical data found in database")
        return False

    except Exception as err:
        coordinator.logger.warning("Error checking for historical data: %s", err)
        return False


async def async_fetch_historical_data(coordinator) -> None:
    """Fetch historical data going back months/years on first run.

    Populates recorder statistics with:
    - Monthly billed usage data for the past 2 years (billing cycle data)
    - Daily usage data for the past 2 years (comprehensive historical data)
    - Hourly usage data for the past 30 days (most detailed recent data)

    Monthly data represents actual billing periods (typically 25th-25th)
    and provides valuable year-over-year comparison data.

    Logs warnings if data retrieval fails but does not raise exceptions
    to avoid blocking the initial coordinator setup.

    NOTE: This method is now scheduled to run in the background after
    initial setup to avoid blocking Home Assistant startup.
    """
    try:
        coordinator.logger.info("Fetching historical water usage data in background...")

        # Fetch data at different resolutions
        end_date = datetime.now()
        loop = asyncio.get_event_loop()

        # Fetch monthly billed usage data - all available history
        coordinator.logger.info("Fetching monthly billed usage data...")
        try:
            # SFPUC typically has 2+ years of billing history
            start_date = end_date - timedelta(days=730)  # 2 years back
            monthly_data = await loop.run_in_executor(
                None,
                coordinator.scraper.get_usage_data,
                start_date,
                end_date,
                "monthly",
            )
            if monthly_data:
                await async_insert_statistics(coordinator, monthly_data)
                coordinator.logger.info(
                    "Fetched %d monthly billing data points", len(monthly_data)
                )
            else:
                coordinator.logger.warning("No monthly billing data retrieved")
        except Exception as err:
            coordinator.logger.warning("Failed to fetch monthly billing data: %s", err)

        # Fetch daily data for the past 2 years (comprehensive historical data)
        # SFPUC limits daily data downloads to ~7-10 days, so we fetch in chunks
        coordinator.logger.info("Fetching daily data in chunks...")
        try:
            all_daily_data = []
            chunk_days = 3  # Fetch 3 days at a time to reduce load
            current_end = end_date
            start_date_2yr = end_date - timedelta(days=730)  # 2 years back

            while current_end > start_date_2yr:
                chunk_start = max(
                    current_end - timedelta(days=chunk_days), start_date_2yr
                )
                coordinator.logger.debug(
                    "Fetching daily chunk from %s to %s",
                    chunk_start.date(),
                    current_end.date(),
                )

                # Retry logic for network errors
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        chunk_data = await loop.run_in_executor(
                            None,
                            coordinator.scraper.get_usage_data,
                            chunk_start,
                            current_end,
                            "daily",
                        )
                        break  # Success, exit retry loop
                    except Exception as err:
                        if attempt < max_retries - 1:
                            coordinator.logger.warning(
                                "Failed to fetch daily chunk (attempt %d/%d): %s, retrying...",
                                attempt + 1,
                                max_retries,
                                err,
                            )
                            await asyncio.sleep(2**attempt)  # Exponential backoff
                        else:
                            coordinator.logger.error(
                                "Failed to fetch daily chunk after %d attempts: %s",
                                max_retries,
                                err,
                            )
                            raise  # Re-raise to stop fetching

                if chunk_data:
                    all_daily_data.extend(chunk_data)
                    coordinator.logger.debug(
                        "Chunk returned %d data points", len(chunk_data)
                    )

                current_end = chunk_start - timedelta(days=1)
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(1.0)

            if all_daily_data:
                await async_insert_statistics(coordinator, all_daily_data)
                coordinator.logger.info(
                    "Fetched %d daily data points total", len(all_daily_data)
                )
            else:
                coordinator.logger.warning("No daily data retrieved")
        except Exception as err:
            coordinator.logger.warning("Failed to fetch daily data: %s", err)

        # Fetch hourly data for the past 30 days (most detailed recent data)
        # SFPUC allows hourly data only for recent dates (typically up to 2 days ago)
        # Fetch in chunks to get complete 30-day hourly history
        coordinator.logger.info("Fetching hourly data in chunks...")
        try:
            all_hourly_data = []
            # Hourly data is available up to ~2 days ago
            # We'll try to fetch 30 days worth, one day at a time
            days_back = 30

            for days_offset in range(
                2, days_back + 2
            ):  # Start from 2 days ago, go back 30 days
                fetch_date = end_date - timedelta(days=days_offset)
                coordinator.logger.debug(
                    "Fetching hourly data for %s",
                    fetch_date.date(),
                )

                # Retry logic for network errors
                max_retries = 3
                hourly_chunk = None
                for attempt in range(max_retries):
                    try:
                        # Fetch one day at a time for hourly data
                        hourly_chunk = await loop.run_in_executor(
                            None,
                            coordinator.scraper.get_usage_data,
                            fetch_date,
                            fetch_date,  # Same day for start and end
                            "hourly",
                        )
                        break  # Success
                    except Exception as err:
                        if attempt < max_retries - 1:
                            coordinator.logger.warning(
                                "Failed to fetch hourly data for %s (attempt %d/%d): %s, retrying...",
                                fetch_date.date(),
                                attempt + 1,
                                max_retries,
                                err,
                            )
                            await asyncio.sleep(2**attempt)  # Exponential backoff
                        else:
                            coordinator.logger.error(
                                "Failed to fetch hourly data for %s after %d attempts: %s",
                                fetch_date.date(),
                                max_retries,
                                err,
                            )
                            # Continue to next day instead of stopping

                if hourly_chunk:
                    all_hourly_data.extend(hourly_chunk)
                    coordinator.logger.debug(
                        "Fetched %d hourly data points for %s",
                        len(hourly_chunk),
                        fetch_date.date(),
                    )

                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.5)

            if all_hourly_data:
                await async_insert_statistics(coordinator, all_hourly_data)
                coordinator.logger.info(
                    "Fetched %d hourly data points total for past 30 days",
                    len(all_hourly_data),
                )
            else:
                coordinator.logger.warning("No hourly data retrieved")
        except Exception as err:
            coordinator.logger.warning("Failed to fetch hourly data: %s", err)

    except Exception as err:
        coordinator.logger.warning("Failed to fetch historical data: %s", err)


async def async_background_historical_fetch(coordinator) -> None:
    """Fetch historical data in background after startup.

    This method runs the historical data fetch process in the background
    to avoid blocking Home Assistant startup. It waits 30 seconds after
    startup before beginning to allow HA to fully initialize.
    """
    try:
        # Wait 30 seconds to let Home Assistant fully start
        await asyncio.sleep(30)

        coordinator.logger.info("Starting background historical data fetch...")
        await async_fetch_historical_data(coordinator)
        coordinator._historical_data_fetched = True
        # Set backfill date to now to avoid re-fetching the same data
        coordinator._last_backfill_date = datetime.now()
        coordinator.logger.info(
            "Background historical data fetch completed successfully"
        )
    except Exception as err:
        coordinator.logger.warning("Background historical data fetch failed: %s", err)
        # Don't set _historical_data_fetched to True so we retry on next coordinator update


async def async_backfill_missing_data(coordinator) -> None:
    """Backfill missing data with 30-day lookback window.

    Runs daily to ensure complete historical data in recorder by:
    1. Checking for missing daily data in the past 30 days
    2. Checking for missing hourly data in the past 7 days
    3. Inserting any missing data points into statistics

    Throttled to run at most once per 24 hours to avoid excessive
    API calls to SFPUC portal.

    Logs warnings if backfilling fails but does not raise exceptions.
    """
    try:
        now = datetime.now()

        # Check if we need to backfill (run this less frequently)
        if coordinator._last_backfill_date and (
            now - coordinator._last_backfill_date
        ) < timedelta(hours=24):
            return

        coordinator.logger.debug("Checking for missing data to backfill...")

        # Look back 30 days for any missing data
        lookback_date = now - timedelta(days=30)

        loop = asyncio.get_event_loop()

        # Check for missing daily data in the lookback period
        try:
            # Retry logic for network errors
            max_retries = 3
            daily_data = None
            for attempt in range(max_retries):
                try:
                    daily_data = await loop.run_in_executor(
                        None,
                        coordinator.scraper.get_usage_data,
                        lookback_date,
                        now,
                        "daily",
                    )
                    break  # Success
                except Exception as err:
                    if attempt < max_retries - 1:
                        coordinator.logger.warning(
                            "Failed to fetch daily backfill data (attempt %d/%d): %s, retrying...",
                            attempt + 1,
                            max_retries,
                            err,
                        )
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        coordinator.logger.error(
                            "Failed to fetch daily backfill data after %d attempts: %s",
                            max_retries,
                            err,
                        )
                        raise

            if daily_data:
                await async_insert_statistics(coordinator, daily_data)
                coordinator.logger.debug(
                    "Backfilled %d daily data points", len(daily_data)
                )
            else:
                coordinator.logger.debug("No daily data found for backfilling")
        except Exception as err:
            coordinator.logger.warning("Failed to backfill daily data: %s", err)

        # Check for missing hourly data in the recent past (last 7 days)
        # Fetch day by day since SFPUC hourly data doesn't work well with date ranges
        try:
            all_hourly_data = []
            # Fetch hourly data from 2 days ago back to 7 days ago
            for days_offset in range(2, 9):  # 2 days ago to 8 days ago (7 days of data)
                fetch_date = now - timedelta(days=days_offset)

                # Retry logic for network errors
                max_retries = 3
                hourly_chunk = None
                for attempt in range(max_retries):
                    try:
                        hourly_chunk = await loop.run_in_executor(
                            None,
                            coordinator.scraper.get_usage_data,
                            fetch_date,
                            fetch_date,  # Same day for start and end
                            "hourly",
                        )
                        break  # Success
                    except Exception as err:
                        if attempt < max_retries - 1:
                            coordinator.logger.warning(
                                "Failed to fetch hourly backfill for %s (attempt %d/%d): %s, retrying...",
                                fetch_date.date(),
                                attempt + 1,
                                max_retries,
                                err,
                            )
                            await asyncio.sleep(2**attempt)  # Exponential backoff
                        else:
                            coordinator.logger.error(
                                "Failed to fetch hourly backfill for %s after %d attempts: %s",
                                fetch_date.date(),
                                max_retries,
                                err,
                            )
                            # Continue to next day

                if hourly_chunk:
                    all_hourly_data.extend(hourly_chunk)
                await asyncio.sleep(0.5)  # Small delay

            if all_hourly_data:
                await async_insert_statistics(coordinator, all_hourly_data)
                coordinator.logger.debug(
                    "Backfilled %d hourly data points", len(all_hourly_data)
                )
            else:
                coordinator.logger.debug("No hourly data found for backfilling")
        except Exception as err:
            coordinator.logger.warning("Failed to backfill hourly data: %s", err)

        coordinator._last_backfill_date = now

    except Exception as err:
        coordinator.logger.warning("Failed to backfill missing data: %s", err)
