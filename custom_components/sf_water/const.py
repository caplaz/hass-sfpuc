"""Constants for the SF Water integration."""

DOMAIN = "sf_water"

# Configuration options
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"

# Default configuration values
DEFAULT_UPDATE_INTERVAL = 60  # minutes (daily update)

# Sensor data keys
KEY_DAILY_USAGE = "daily_usage"
KEY_LAST_UPDATED = "last_updated"

# Sensor types configuration
SENSOR_TYPES = {
    "daily_usage": {
        "name": "Daily Water Usage",
        "unit": "gal",
        "icon": "mdi:water",
        "device_class": "water",
    },
}
