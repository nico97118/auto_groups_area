"""Constants for the Auto Groups by Area integration."""

from homeassistant.const import Platform

DOMAIN = "auto_groups_area"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

# Group naming
GROUP_PREFIX = "area_"

# Options
# New-style actuator selection (replaces per-domain checkboxes).
CONF_ACTUATOR_DOMAINS = "actuator_domains"

CONF_ENABLE_LIGHTS = "enable_lights"
CONF_ENABLE_SWITCHES = "enable_switches"
CONF_ENABLE_SENSORS = "enable_sensors"
CONF_ENABLE_BINARY_SENSORS = "enable_binary_sensors"
CONF_GROUP_PREFIX = "group_prefix"
CONF_CREATE_WHEN_EMPTY = "create_when_empty"
CONF_INCLUDE_DEVICE_AREA = "include_device_area"
CONF_INCLUDED_AREAS = "included_areas"
CONF_EXCLUDED_AREAS = "excluded_areas"
CONF_EXCLUDED_ENTITIES = "excluded_entities"

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
AGGREGATION_LAST = "last"

DEFAULT_OPTIONS: dict[str, object] = {
    # New-style actuator selection (defaults to lights only).
    CONF_ACTUATOR_DOMAINS: ["light"],
    CONF_ENABLE_LIGHTS: True,
    # Default to off to avoid surprising upgrades.
    CONF_ENABLE_SWITCHES: False,
    CONF_ENABLE_SENSORS: True,
    CONF_ENABLE_BINARY_SENSORS: True,
    CONF_GROUP_PREFIX: GROUP_PREFIX,
    CONF_CREATE_WHEN_EMPTY: False,
    CONF_INCLUDE_DEVICE_AREA: True,
    # Stored as a list of area_id (via UI selectors). Backward compatible with
    # older string-based configs in the runtime filters.
    CONF_INCLUDED_AREAS: [],
    CONF_EXCLUDED_AREAS: [],
    CONF_EXCLUDED_ENTITIES: [],
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
    merged = {**DEFAULT_OPTIONS, **(options or {})}

    # Backward compatibility: if actuator_domains isn't present, derive from legacy
    # per-domain checkboxes.
    raw_domains = merged.get(CONF_ACTUATOR_DOMAINS)
    if isinstance(raw_domains, list) and all(isinstance(v, str) for v in raw_domains):
        merged[CONF_ACTUATOR_DOMAINS] = [v for v in raw_domains if v]
        return merged

    domains: list[str] = []
    if bool(merged.get(CONF_ENABLE_LIGHTS, True)):
        domains.append("light")
    if bool(merged.get(CONF_ENABLE_SWITCHES, False)):
        domains.append("switch")
    merged[CONF_ACTUATOR_DOMAINS] = domains
    return merged


def enabled_platforms(options: dict) -> list[Platform]:
    """Return platforms enabled by options."""
    opts = merged_options(options)
    platforms: list[Platform] = []
    actuator_domains = opts.get(CONF_ACTUATOR_DOMAINS, [])
    if isinstance(actuator_domains, list) and "light" in actuator_domains:
        platforms.append(Platform.LIGHT)
    if isinstance(actuator_domains, list) and "switch" in actuator_domains:
        platforms.append(Platform.SWITCH)
    if opts[CONF_ENABLE_BINARY_SENSORS]:
        platforms.append(Platform.BINARY_SENSOR)
    if opts[CONF_ENABLE_SENSORS]:
        platforms.append(Platform.SENSOR)
    return platforms
