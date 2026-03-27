"""The Auto Groups by Area integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    PLATFORMS,
    enabled_platforms,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_RELOAD = "reload"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Auto Groups by Area component."""
    if DOMAIN not in config:
        return True

    _LOGGER.debug("Importing %s from configuration.yaml", DOMAIN)
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data=config[DOMAIN] or {}
        )
    )
    return True


async def _async_reload_all_groups(hass: HomeAssistant) -> None:
    """Force a refresh of all groups for all config entries."""
    if DOMAIN not in hass.data:
        raise HomeAssistantError("Integration not loaded")

    tasks = []
    entry_ids: list[str] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_ids.append(entry.entry_id)
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        coordinators = (
            entry_data.get("coordinators", []) if isinstance(entry_data, dict) else []
        )
        for coordinator in coordinators:
            update = getattr(coordinator, "async_update_all_groups", None)
            if update is not None:
                tasks.append(update())

    if not tasks:
        _LOGGER.warning(
            "Reload requested, but no coordinators found (entries=%d)", len(entry_ids)
        )
        return

    _LOGGER.info(
        "Reloading all groups (entries=%d, coordinators=%d)",
        len(entry_ids),
        len(tasks),
    )

    import asyncio  # noqa: PLC0415

    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        _LOGGER.error("Reload completed with %d error(s); check logs", len(errors))
        for idx, err in enumerate(errors, start=1):
            _LOGGER.exception("Reload error #%d", idx, exc_info=err)
    else:
        _LOGGER.info("Reload completed successfully")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register services once.
    global_data = hass.data[DOMAIN].setdefault("_global", {})
    if not global_data.get("services_registered"):

        async def _handle_reload(_: ServiceCall) -> None:
            await _async_reload_all_groups(hass)

        hass.services.async_register(DOMAIN, SERVICE_RELOAD, _handle_reload)
        global_data["services_registered"] = True

    platforms = enabled_platforms(entry.options)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if isinstance(entry_data, dict):
        coordinators = entry_data.get("coordinators", [])
        for coordinator in coordinators:
            await coordinator.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # If no entries remain, remove the service and cleanup.
        if not hass.config_entries.async_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
        domain_data = hass.data.get(DOMAIN)
        if isinstance(domain_data, dict) and set(domain_data.keys()) <= {"_global"}:
            hass.data.pop(DOMAIN, None)
    return unload_ok
