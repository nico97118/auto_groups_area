"""Optional, non-destructive area assignment for generated groups."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

from .const import CONF_ASSIGN_GROUP_AREA, DOMAIN


@callback
def async_assign_group_area(hass: HomeAssistant, entity_id: str, area_id: str) -> None:
    """Assign an unassigned generated entity without overriding user choices."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or entry.platform != DOMAIN or entry.area_id is not None:
        return
    config = hass.config_entries.async_get_entry(entry.config_entry_id)
    if config is None or not config.options.get(CONF_ASSIGN_GROUP_AREA, False):
        return
    if ar.async_get(hass).async_get_area(area_id) is not None:
        registry.async_update_entity(entity_id, area_id=area_id)
