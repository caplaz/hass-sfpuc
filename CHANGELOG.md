# Changelog

## 1.0.0 (2025-11-09)

### Features

- **SFPUC Water Usage Integration**: Monitor San Francisco Public Utilities Commission water usage
- **Daily Water Usage Sensor**: Daily consumption tracking in gallons
- **SFPUC Portal Integration**: Secure authentication and data scraping from SFPUC portal
- **Energy Dashboard Support**: Automatic statistics insertion for Home Assistant Energy dashboard
- **Configuration Flow**: User-friendly setup through Home Assistant UI
- **Multi-language Support**: English and Spanish translations

### Technical Details

- **Home Assistant 2023.1+**: Compatible with modern Home Assistant installations
- **HACS Compatible**: Proper manifest structure for Home Assistant Community Store
- **Security First**: Secure credential storage and HTTPS-only communications
- **Code Quality**: Comprehensive pre-commit hooks (black, isort, flake8, mypy, bandit, codespell, yamllint)
- **Modular Architecture**: Clean separation between coordinator, sensor, and configuration components
- **Type Safety**: Full type annotations and mypy compliance

### Requirements

- **Python Dependencies**: requests, beautifulsoup4, voluptuous
- **Home Assistant**: 2023.1.0 or later
- **SFPUC Account**: Valid SFPUC water service account credentials
