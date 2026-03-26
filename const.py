"""Constants for the Auto Groups by Area integration."""

from homeassistant.const import Platform

DOMAIN = "auto_groups_area"

# Platforms
PLATFORMS: list[Platform] = [Platform.LIGHT]

# Default configuration
DEFAULT_DOMAINS = ["light"]

# Group naming
GROUP_PREFIX = "area_"
