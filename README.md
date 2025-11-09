# SF Water for Home Assistant

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![CI][ci-shield]][ci]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

A Home Assistant custom integration for monitoring San Francisco water usage from SFPUC (San Francisco Public Utilities Commission). This integration connects to your SFPUC account to fetch historical water usage data and provides it as sensors in Home Assistant.

![SF Water][logo]

## Why This Integration?

SFPUC provides water usage data through their online portal, but accessing this data programmatically allows for better integration with smart home systems. This integration automatically fetches your water usage data and stores it in Home Assistant's database, similar to how energy monitoring integrations like Opower work.

## Features

- 💧 **Daily Water Usage**: Track daily water consumption in gallons
- 📊 **Historical Data**: Access to historical usage data from SFPUC
- 🔐 **Secure Authentication**: Direct connection to SFPUC portal with your credentials
- 🗄️ **Database Storage**: Data stored locally in Home Assistant database
- ⏰ **Configurable Updates**: Set custom update intervals (15-1440 minutes)
- 🌍 **Multilingual Support**: Available in English and Spanish
- 🔄 **Automatic Updates**: Periodic data fetching and sensor updates
- 📈 **Cumulative Tracking**: State class TOTAL_INCREASING for proper energy monitoring integration

## Installation

### Method 1: HACS (Recommended)

HACS (Home Assistant Community Store) is the easiest way to install and manage custom integrations.

#### Prerequisites

- [HACS](https://hacs.xyz/) must be installed in your Home Assistant instance
- Home Assistant version 2023.1.0 or higher
- Valid SFPUC account credentials

#### Installation Steps

1. **Open HACS**: Go to HACS in your Home Assistant sidebar
2. **Navigate to Integrations**: Click on "Integrations"
3. **Search and Install**:
   - Search for "SF Water" in HACS
   - Click on it and select "Download"
   - Choose the latest version
4. **Restart Home Assistant**: Required for the integration to load

### Method 2: Manual Installation

#### Prerequisites

- Home Assistant version 2023.1.0 or higher
- Valid SFPUC account credentials

#### Installation Steps

1. **Download the Integration**:
   ```bash
   wget https://github.com/caplaz/hass-sfpuc/archive/refs/tags/v1.0.0.zip
   unzip v1.0.0.zip
   ```

2. **Copy Files**:
   ```bash
   cp -r hass-sfpuc-1.0.0/custom_components/sf_water /config/custom_components/
   ```

3. **Restart Home Assistant**:
   - Go to Settings → System → Restart
   - Wait for Home Assistant to restart

## Configuration

### Initial Setup

1. **Add Integration**: Go to Settings → Devices & Services → Add Integration
2. **Search**: Type "SF Water" in the search box
3. **Select**: Click on "SF Water" from the results
4. **Configure**:
   - **SFPUC Username**: Your SFPUC account username (typically account number or email)
   - **SFPUC Password**: Your SFPUC portal password
   - **Update Interval**: How often to fetch data (15-1440 minutes, default 60)
5. **Submit**: The integration will test your credentials and create the sensor

### Configuration Options

After setup, you can modify settings by:

1. Going to Settings → Devices & Services
2. Finding "SF Water" in your integrations list
3. Clicking "Configure" to change the update interval

## Usage

### Sensors Created

The integration creates one main sensor:

- **SF Water Daily Usage** (`sensor.sf_water_daily_usage`)
  - **State**: Daily water usage in gallons
  - **Device Class**: `water`
  - **State Class**: `total_increasing`
  - **Unit**: `gal` (gallons)

### Dashboard Integration

#### Add to Energy Dashboard

1. Go to Settings → Dashboards → Energy
2. Click "Add Consumption" or "Add Return"
3. Select the SF Water sensor
4. Configure as water consumption

#### Add Sensor Card

1. Go to your dashboard
2. Click "Add Card" → "Sensor"
3. Select `sensor.sf_water_daily_usage`
4. Customize display options

### Automations

You can create automations based on water usage:

```yaml
# Example: Alert on high daily usage
alias: "High Water Usage Alert"
triggers:
  - platform: numeric_state
    entity_id: sensor.sf_water_daily_usage
    above: 500  # gallons
actions:
  - service: notify.mobile_app
    data:
      message: "High water usage detected: {{ states('sensor.sf_water_daily_usage') }} gallons today"
```

## Data Storage

- **Local Storage**: All data is stored in your Home Assistant database
- **Historical Data**: Full historical data from SFPUC is preserved
- **Privacy**: Credentials are encrypted and stored securely
- **No External Services**: Data fetching happens locally on your Home Assistant instance

## Troubleshooting

### Common Issues

#### Authentication Failed
- **Cause**: Invalid username/password or SFPUC portal changes
- **Solution**: Verify your SFPUC credentials and try reconfiguring the integration

#### No Data Updates
- **Cause**: SFPUC portal issues or network connectivity
- **Solution**: Check SFPUC website manually and verify internet connection

#### Sensor Unavailable
- **Cause**: Integration unable to fetch data
- **Solution**: Check Home Assistant logs for error messages

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  logs:
    custom_components.sf_water: debug
```

## Technical Details

### Requirements

- **Python Packages**:
  - `requests>=2.25.1`
  - `beautifulsoup4>=4.9.3`
  - `voluptuous>=0.13.1`

### Supported Languages

- English (en)
- Spanish (es)

### API Usage

- Connects to SFPUC portal using secure HTTPS
- Downloads Excel files containing usage data
- Parses data locally without external API calls
- Respects SFPUC's terms of service and rate limits

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/caplaz/hass-sfpuc.git
   cd hass-sfpuc
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Run tests:
   ```bash
   python -m pytest
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/caplaz/hass-sfpuc/issues)
- **Discussions**: [GitHub Discussions](https://github.com/caplaz/hass-sfpuc/discussions)
- **Documentation**: [Full Documentation](https://github.com/caplaz/hass-sfpuc/wiki)

## Credits

- **Author**: caplaz
- **Inspired by**: Opower and other utility monitoring integrations
- **SFPUC**: San Francisco Public Utilities Commission for providing water service data

---

*This integration is not officially affiliated with or endorsed by the San Francisco Public Utilities Commission (SFPUC). Use at your own risk and in accordance with SFPUC's terms of service.*