"""Constants for the Auto Groups by Area integration."""

from homeassistant.const import Platform

DOMAIN = "auto_groups_area"

# Platforms
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.BINARY_SENSOR, Platform.SENSOR]

# Group naming
GROUP_PREFIX = "area_"

# Options
CONF_ENABLE_LIGHTS = "enable_lights"
CONF_ENABLE_SENSORS = "enable_sensors"
CONF_ENABLE_BINARY_SENSORS = "enable_binary_sensors"
CONF_GROUP_PREFIX = "group_prefix"
CONF_CREATE_WHEN_EMPTY = "create_when_empty"
CONF_INCLUDE_DEVICE_AREA = "include_device_area"
CONF_INCLUDED_AREAS = "included_areas"
CONF_EXCLUDED_AREAS = "excluded_areas"

CONF_ENABLE_BS_MOTION = "enable_binary_sensor_motion"
CONF_ENABLE_BS_PRESENCE = "enable_binary_sensor_presence"
CONF_ENABLE_BS_OPENING = "enable_binary_sensor_opening"
CONF_ENABLE_BS_OPENCLOSE = "enable_binary_sensor_openclose"

CONF_ILLUMINANCE_AGGREGATION = "illuminance_aggregation"
CONF_HUMIDITY_AGGREGATION = "humidity_aggregation"
CONF_TEMPERATURE_AGGREGATION = "temperature_aggregation"

AGGREGATION_MAX = "max"
AGGREGATION_MEAN = "mean"
AGGREGATION_MIN = "min"

DEFAULT_OPTIONS: dict[str, object] = {
    CONF_ENABLE_LIGHTS: True,
    CONF_ENABLE_SENSORS: True,
    CONF_ENABLE_BINARY_SENSORS: True,
    CONF_GROUP_PREFIX: GROUP_PREFIX,
    CONF_CREATE_WHEN_EMPTY: False,
    CONF_INCLUDE_DEVICE_AREA: True,
    CONF_INCLUDED_AREAS: "",
    CONF_EXCLUDED_AREAS: "",
    CONF_ENABLE_BS_MOTION: True,
    CONF_ENABLE_BS_PRESENCE: True,
    CONF_ENABLE_BS_OPENING: True,
    CONF_ENABLE_BS_OPENCLOSE: True,
    CONF_ILLUMINANCE_AGGREGATION: AGGREGATION_MAX,
    CONF_HUMIDITY_AGGREGATION: AGGREGATION_MEAN,
    CONF_TEMPERATURE_AGGREGATION: AGGREGATION_MEAN,
}


def merged_options(options: dict) -> dict[str, object]:
    """Return integration options with defaults applied."""
    return {**DEFAULT_OPTIONS, **(options or {})}


def enabled_platforms(options: dict) -> list[Platform]:
    """Return platforms enabled by options."""
    opts = merged_options(options)
    platforms: list[Platform] = []
    if opts[CONF_ENABLE_LIGHTS]:
        platforms.append(Platform.LIGHT)
    if opts[CONF_ENABLE_BINARY_SENSORS]:
        platforms.append(Platform.BINARY_SENSOR)
    if opts[CONF_ENABLE_SENSORS]:
        platforms.append(Platform.SENSOR)
    return platforms
