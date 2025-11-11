"""SFPUC web scraper for water usage data."""

from datetime import datetime
import logging
from typing import Any

from bs4 import BeautifulSoup
import requests

_LOGGER = logging.getLogger(__name__)


class SFPUCScraper:
    """SF PUC water usage data scraper.

    This class handles web scraping of water usage data from the SFPUC
    (San Francisco Public Utilities Commission) online portal at
    myaccount-water.sfpuc.org. It manages authentication, form submission,
    and parsing of downloaded usage data in various resolutions.
    """

    def __init__(self, username: str, password: str) -> None:
        """Initialize the scraper.

        Args:
            username: SFPUC account username/account number.
            password: SFPUC account password.
        """
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
        """Authenticate with SFPUC portal.

        Performs ASP.NET authentication with the SFPUC portal by:
        1. Fetching the login page to extract ASP.NET view state and event validation tokens
        2. Submitting credentials via POST with the extracted tokens
        3. Analyzing response for success/failure indicators

        Returns:
            True if login was successful, False otherwise.
        """
        try:
            _LOGGER.debug(
                "Starting SFPUC login process for user: %s", self.username[:3] + "***"
            )

            # GET the login page to extract ViewState
            login_url = f"{self.base_url}/"
            _LOGGER.debug("Fetching login page: %s", login_url)
            response = self.session.get(login_url)
            _LOGGER.debug("Login page response status: %s", response.status_code)

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract hidden form fields
            viewstate = soup.find("input", {"name": "__VIEWSTATE"})
            eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})
            viewstate_generator = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})

            if not viewstate or not eventvalidation:
                _LOGGER.warning("Failed to extract form tokens from login page")
                return False

            _LOGGER.debug("Successfully extracted form tokens")

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
            _LOGGER.debug("Submitting login form")
            response = self.session.post(
                login_url, data=login_data, allow_redirects=True
            )
            _LOGGER.debug(
                "Login response status: %s, URL: %s", response.status_code, response.url
            )

            # Check if login successful
            # Look for indicators of successful login vs failure
            if response.status_code == 200:
                # Check for common success indicators
                success_indicators = [
                    "MY_ACCOUNT_RSF.aspx" in response.url,
                    "Welcome" in response.text,
                    "Dashboard" in response.text,
                    "Account" in response.text,
                    "Usage" in response.text,
                    "Logout" in response.text,
                ]

                # Check for failure indicators
                failure_indicators = [
                    "Invalid" in response.text and "password" in response.text.lower(),
                    "Login failed" in response.text,
                    "Authentication failed" in response.text,
                    "Error" in response.text and "login" in response.text.lower(),
                    "Please try again" in response.text,
                    response.url.endswith("/"),  # Still on login page
                ]

                success_score = sum(success_indicators)
                failure_score = sum(failure_indicators)

                _LOGGER.debug(
                    "Login analysis - Success indicators: %d, Failure indicators: %d",
                    success_score,
                    failure_score,
                )
                _LOGGER.debug("Response URL: %s", response.url)
                _LOGGER.debug(
                    "Response contains 'Welcome': %s", "Welcome" in response.text
                )
                _LOGGER.debug(
                    "Response contains 'Invalid': %s", "Invalid" in response.text
                )

                if success_score > 0 and failure_score == 0:
                    _LOGGER.info(
                        "SFPUC login successful for user: %s", self.username[:3] + "***"
                    )
                    return True
                else:
                    _LOGGER.warning(
                        "SFPUC login failed - success_score: %d, failure_score: %d",
                        success_score,
                        failure_score,
                    )
                    return False
            else:
                _LOGGER.warning(
                    "SFPUC login failed with status code: %s", response.status_code
                )
                return False

        except Exception as e:
            _LOGGER.error(
                "Exception during SFPUC login for user %s: %s",
                self.username[:3] + "***",
                e,
            )
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
            _LOGGER.debug(
                "Fetching %s usage data from %s to %s",
                resolution,
                start_date.date(),
                end_date.date(),
            )

            # Navigate to appropriate usage page based on resolution
            if resolution == "hourly":
                usage_url = f"{self.base_url}/USE_HOURLY.aspx"
                data_type = "Hourly+Use"
            elif resolution == "daily":
                usage_url = f"{self.base_url}/USE_DAILY.aspx"
                data_type = "Daily+Use"
            elif resolution == "monthly":
                # Use the billed usage page for monthly data
                usage_url = f"{self.base_url}/USE_BILLED.aspx"
                data_type = "Billed+Use"
            else:
                _LOGGER.error("Invalid resolution specified: %s", resolution)
                return None

            _LOGGER.debug("Navigating to usage page: %s", usage_url)
            response = self.session.get(usage_url)
            _LOGGER.debug("Usage page response status: %s", response.status_code)

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract form tokens
            tokens = {}
            form = soup.find("form")
            if form:
                for inp in form.find_all("input"):
                    name = inp.get("name")
                    if name:
                        tokens[name] = inp.get("value", "")

            _LOGGER.debug("Extracted %d form tokens", len(tokens))

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
            if resolution == "monthly":
                download_url = f"{self.base_url}/USE_BILLED.aspx"
            else:
                download_url = f"{self.base_url}/USE_{resolution.upper()}.aspx"
            _LOGGER.debug("Triggering Excel download from: %s", download_url)
            response = self.session.post(
                download_url, data=tokens, allow_redirects=True
            )
            _LOGGER.debug(
                "Download response status: %s, URL: %s",
                response.status_code,
                response.url,
            )

            if "TRANSACTIONS_EXCEL_DOWNLOAD.aspx" in response.url:
                # Parse the Excel data
                content = response.content.decode("utf-8", errors="ignore")
                lines = content.split("\n")
                _LOGGER.debug("Downloaded content has %d lines", len(lines))

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
                                    # Try multiple formats for hourly data
                                    timestamp = None
                                    # First try full datetime format (for tests)
                                    try:
                                        timestamp = datetime.strptime(
                                            timestamp_str, "%m/%d/%Y %H:%M:%S"
                                        )
                                    except ValueError:
                                        pass

                                    # If that fails, try AM/PM format without date (real SFPUC format)
                                    if timestamp is None:
                                        try:
                                            # Handle AM/PM format like "12 AM", "1 PM"
                                            if timestamp_str.upper().endswith(
                                                " AM"
                                            ) or timestamp_str.upper().endswith(" PM"):
                                                hour_str = timestamp_str.split()[0]
                                                am_pm = timestamp_str.split()[1].upper()
                                                hour = int(hour_str)
                                                if am_pm == "PM" and hour != 12:
                                                    hour += 12
                                                elif am_pm == "AM" and hour == 12:
                                                    hour = 0
                                                # Use the requested end_date for hourly data
                                                # SFPUC typically shows hourly data up to 2 days ago
                                                # Use end_date from the request instead of assuming today
                                                request_date = end_date.date()
                                                timestamp = datetime.combine(
                                                    request_date,
                                                    datetime.min.time().replace(
                                                        hour=hour
                                                    ),
                                                )
                                        except (ValueError, IndexError):
                                            pass

                                    if timestamp is None:
                                        _LOGGER.debug(
                                            "Failed to parse hourly timestamp: %s",
                                            timestamp_str,
                                        )
                                        continue

                                elif resolution == "daily":
                                    # Try multiple formats for daily data
                                    timestamp = None
                                    # First try full date format (for tests)
                                    try:
                                        timestamp = datetime.strptime(
                                            timestamp_str, "%m/%d/%Y"
                                        )
                                    except ValueError:
                                        pass

                                    # If that fails, try MM/DD format without year (real SFPUC format)
                                    # Use the year from the requested start_date to avoid defaulting to current year
                                    if timestamp is None:
                                        try:
                                            month, day = map(
                                                int, timestamp_str.split("/")
                                            )
                                            # Infer year from requested date range
                                            # If the month is near the end of year and we're requesting data
                                            # that spans year boundaries, we need to handle the year transition
                                            requested_year = start_date.year
                                            timestamp = datetime(
                                                requested_year, month, day
                                            )

                                            # Handle year boundaries: if parsed date is before start_date
                                            # and we're in December/January, it might be next year
                                            if (
                                                timestamp < start_date
                                                and start_date.month == 12
                                                and month == 1
                                            ):
                                                timestamp = datetime(
                                                    requested_year + 1, month, day
                                                )
                                            # Or if parsed date is after end_date and we're crossing into
                                            # previous year (Jan requesting Dec data)
                                            elif (
                                                timestamp > end_date
                                                and end_date.month == 1
                                                and month == 12
                                            ):
                                                timestamp = datetime(
                                                    requested_year - 1, month, day
                                                )
                                        except (ValueError, IndexError):
                                            pass

                                    if timestamp is None:
                                        _LOGGER.debug(
                                            "Failed to parse daily timestamp: %s",
                                            timestamp_str,
                                        )
                                        continue

                                elif resolution == "monthly":
                                    # Try multiple formats for monthly data
                                    timestamp = None
                                    # First try MM/YYYY format (for tests)
                                    try:
                                        timestamp = datetime.strptime(
                                            timestamp_str, "%m/%Y"
                                        )
                                    except ValueError:
                                        pass

                                    # If that fails, try "Mon YY" format (real SFPUC format like "Dec 23")
                                    if timestamp is None:
                                        try:
                                            # Parse "Dec 23" format - month abbreviation and 2-digit year
                                            month_name, year_str = timestamp_str.split()
                                            # Convert month name to number
                                            month = datetime.strptime(
                                                month_name, "%b"
                                            ).month
                                            # Convert 2-digit year to 4-digit (assuming 2000s)
                                            year = 2000 + int(year_str)
                                            timestamp = datetime(year, month, 1)
                                        except (ValueError, IndexError):
                                            pass

                                    if timestamp is None:
                                        _LOGGER.debug(
                                            "Failed to parse monthly timestamp: %s",
                                            timestamp_str,
                                        )
                                        continue

                                usage_data.append(
                                    {
                                        "timestamp": timestamp,
                                        "usage": usage,
                                        "resolution": resolution,
                                    }
                                )
                            except (ValueError, IndexError) as e:
                                _LOGGER.debug(
                                    "Failed to parse line: %s, error: %s",
                                    line.strip(),
                                    e,
                                )
                                continue

                if usage_data:
                    dates = [item["timestamp"] for item in usage_data]
                    _LOGGER.info(
                        "Successfully parsed %d %s data points (from %s to %s)",
                        len(usage_data),
                        resolution,
                        min(dates).strftime("%Y-%m-%d") if dates else "N/A",
                        max(dates).strftime("%Y-%m-%d") if dates else "N/A",
                    )
                else:
                    _LOGGER.info("Successfully parsed 0 %s data points", resolution)
                return usage_data
            else:
                _LOGGER.warning("Download failed - unexpected URL: %s", response.url)
                return None

        except Exception as e:
            _LOGGER.error(
                "Exception during %s data retrieval for user %s: %s",
                resolution,
                self.username[:3] + "***",
                e,
            )
            return None

    def get_daily_usage(self) -> float | None:
        """Get today's water usage in gallons (legacy method for backward compatibility).

        Convenience method that aggregates hourly usage data for the current day.

        Returns:
            Total water usage for today in gallons, or None if data retrieval fails.
        """
        today = datetime.now()
        data = self.get_usage_data(today, today, "hourly")
        if data:
            # Sum all hourly usage for the day
            return sum(item["usage"] for item in data)
        return None
