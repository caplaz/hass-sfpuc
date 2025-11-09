"""Config flow for SF Water integration."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
import voluptuous as vol

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SFWaterConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for SF Water."""

    VERSION = 1
    DOMAIN = DOMAIN

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate credentials by attempting login
                from .coordinator import SFPUCScraper

                scraper = SFPUCScraper(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                if scraper.login():
                    return self.async_create_entry(
                        title="SF Water",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.error("Error during config flow: %s", e)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SFWaterOptionsFlowHandler(config_entry)


class SFWaterOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for SF Water."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        # No configurable options - update interval is fixed for daily data
        return self.async_create_entry(title="", data={})
