from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.auto_groups_area.const import (
    AGGREGATION_LAST,
    CONF_ENABLE_BINARY_SENSORS,
    CONF_ENABLE_SENSORS,
    CONF_ENABLE_SWITCHES,
    CONF_EXCLUDED_ENTITIES,
    CONF_HUMIDITY_AGGREGATION,
)


async def test_options_flow_multistep(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert any(getattr(key, "schema", None) == CONF_ENABLE_SWITCHES for key in schema)

    # Keep binary_sensors enabled, disable sensors => should go to binary_sensors then advanced.
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_SENSORS: False, CONF_ENABLE_BINARY_SENSORS: True},
    )
    assert result2["type"] == "form"
    assert result2["step_id"] == "binary_sensors"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input={}
    )
    assert result3["type"] == "form"
    assert result3["step_id"] == "advanced"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"], user_input={CONF_EXCLUDED_ENTITIES: []}
    )
    assert result4["type"] == "create_entry"


async def test_options_flow_sensors_step(
    hass: HomeAssistant, setup_integration
) -> None:
    entry = setup_integration

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_SENSORS: True, CONF_ENABLE_BINARY_SENSORS: False},
    )
    assert result2["type"] == "form"
    assert result2["step_id"] == "sensors"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input={CONF_HUMIDITY_AGGREGATION: AGGREGATION_LAST}
    )
    assert result3["type"] == "form"
    assert result3["step_id"] == "advanced"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"], user_input={}
    )
    assert result4["type"] == "create_entry"

    # Verify option got stored.
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated is not None
    assert updated.options[CONF_HUMIDITY_AGGREGATION] == AGGREGATION_LAST
