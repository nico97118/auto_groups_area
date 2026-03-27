from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import DOMAIN


async def test_reload_service_creates_groups_after_changes(
    hass: HomeAssistant, setup_integration
) -> None:
    await async_setup_component(hass, "light", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Studio")

    # No lights yet -> no group
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("light.area_studio") is None

    # Add a light after setup, then reload -> group appears
    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "later", area_id=area.id)
    hass.states.async_set("light.demo_later", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("light.area_studio") is not None
