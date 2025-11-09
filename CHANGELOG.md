# Changelog

## 1.0.0 (2025-11-09)

### Features

- **SFPUC Water Usage Integration**: Monitor San Francisco Public Utilities Commission water usage
- **Historical Data Fetching**: Downloads historical water usage data going back months/years on initial setup
- **Multiple Data Resolutions**: Fetches data at hourly, daily, and monthly intervals
- **Automatic Backfilling**: 30-day lookback window to fill missing data gaps
- **Multi-Resolution Sensors**: Daily, hourly, and monthly usage sensors for comprehensive monitoring
- **SFPUC Portal Integration**: Secure authentication and data scraping from SFPUC portal
- **Energy Dashboard Support**: Automatic statistics insertion for Home Assistant Energy dashboard with multiple resolutions
- **Configuration Flow**: User-friendly setup through Home Assistant UI
- **Multi-language Support**: English and Spanish translations

### Technical Details

- **Home Assistant 2023.1+**: Compatible with modern Home Assistant installations
- **HACS Compatible**: Proper manifest structure for Home Assistant Community Store
- **Security First**: Secure credential storage and HTTPS-only communications
- **Code Quality**: Comprehensive pre-commit hooks (black, isort, flake8, mypy, bandit, codespell, yamllint)
- **Modular Architecture**: Clean separation between coordinator, sensor, and configuration components
- **Type Safety**: Full type annotations and mypy compliance
- **Intelligent Backfilling**: Periodic checks for missing data with configurable lookback window
- **Resolution-Based Storage**: Proper statistics metadata for each time resolution
- **Enhanced Coordinator**: Historical data fetching on first run with incremental updates
- **Update Frequency**: Fixed 12-hour intervals for daily water usage data (following Home Assistant utility integration patterns)

### Requirements

- **Python Dependencies**: requests, beautifulsoup4, voluptuous
- **Home Assistant**: 2023.1.0 or later
- **SFPUC Account**: Valid SFPUC water service account credentials
