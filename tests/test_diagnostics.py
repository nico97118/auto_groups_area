from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.auto_groups_area.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from custom_components.auto_groups_area.const import DOMAIN


async def test_config_entry_diagnostics(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration
    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry"]["entry_id"] == entry.entry_id
    assert "entry_options" in diag
    assert "runtime" in diag


async def test_device_diagnostics(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Test")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={("demo", "dev")})
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "lamp", device_id=device.id)

    diag = await async_get_device_diagnostics(hass, entry, device)
    assert diag["device"]["id"] == device.id
    assert isinstance(diag["entities"], list)
