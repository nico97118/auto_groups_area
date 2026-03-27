"""Config flow for Auto Groups by Area integration."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AGGREGATION_MAX,
    AGGREGATION_MEAN,
    AGGREGATION_MIN,
    CONF_CREATE_WHEN_EMPTY,
    CONF_ENABLE_BINARY_SENSORS,
    CONF_ENABLE_BS_MOTION,
    CONF_ENABLE_BS_OPENCLOSE,
    CONF_ENABLE_BS_OPENING,
    CONF_ENABLE_BS_PRESENCE,
    CONF_ENABLE_LIGHTS,
    CONF_ENABLE_SENSORS,
    CONF_EXCLUDED_AREAS,
    CONF_GROUP_PREFIX,
    CONF_HUMIDITY_AGGREGATION,
    CONF_ILLUMINANCE_AGGREGATION,
    CONF_INCLUDED_AREAS,
    CONF_INCLUDE_DEVICE_AREA,
    CONF_TEMPERATURE_AGGREGATION,
    DEFAULT_OPTIONS,
    DOMAIN,
)


class AutoGroupsAreaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Auto Groups by Area."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Auto Groups by Area", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Auto Groups by Area", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return AutoGroupsAreaOptionsFlow(config_entry)


class AutoGroupsAreaOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Auto Groups by Area."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # `OptionsFlow` may expose `config_entry` as a read-only property in some
        # Home Assistant versions, so keep our own reference.
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        opts = {**DEFAULT_OPTIONS, **dict(self._config_entry.options)}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_ENABLE_LIGHTS, default=opts[CONF_ENABLE_LIGHTS]): bool,
                vol.Optional(CONF_ENABLE_BINARY_SENSORS, default=opts[CONF_ENABLE_BINARY_SENSORS]): bool,
                vol.Optional(CONF_ENABLE_SENSORS, default=opts[CONF_ENABLE_SENSORS]): bool,
                vol.Optional(CONF_GROUP_PREFIX, default=opts[CONF_GROUP_PREFIX]): str,
                vol.Optional(CONF_CREATE_WHEN_EMPTY, default=opts[CONF_CREATE_WHEN_EMPTY]): bool,
                vol.Optional(CONF_INCLUDE_DEVICE_AREA, default=opts[CONF_INCLUDE_DEVICE_AREA]): bool,
                vol.Optional(CONF_INCLUDED_AREAS, default=opts[CONF_INCLUDED_AREAS]): str,
                vol.Optional(CONF_EXCLUDED_AREAS, default=opts[CONF_EXCLUDED_AREAS]): str,
                vol.Optional(CONF_ENABLE_BS_MOTION, default=opts[CONF_ENABLE_BS_MOTION]): bool,
                vol.Optional(CONF_ENABLE_BS_PRESENCE, default=opts[CONF_ENABLE_BS_PRESENCE]): bool,
                vol.Optional(CONF_ENABLE_BS_OPENING, default=opts[CONF_ENABLE_BS_OPENING]): bool,
                vol.Optional(CONF_ENABLE_BS_OPENCLOSE, default=opts[CONF_ENABLE_BS_OPENCLOSE]): bool,
                vol.Optional(
                    CONF_ILLUMINANCE_AGGREGATION,
                    default=opts[CONF_ILLUMINANCE_AGGREGATION],
                ): vol.In([AGGREGATION_MAX, AGGREGATION_MEAN, AGGREGATION_MIN]),
                vol.Optional(
                    CONF_HUMIDITY_AGGREGATION,
                    default=opts[CONF_HUMIDITY_AGGREGATION],
                ): vol.In([AGGREGATION_MAX, AGGREGATION_MEAN, AGGREGATION_MIN]),
                vol.Optional(
                    CONF_TEMPERATURE_AGGREGATION,
                    default=opts[CONF_TEMPERATURE_AGGREGATION],
                ): vol.In([AGGREGATION_MAX, AGGREGATION_MEAN, AGGREGATION_MIN]),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
