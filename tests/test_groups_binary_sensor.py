from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import DOMAIN


async def test_binary_sensor_openclose_on_if_any_on(hass: HomeAssistant, setup_integration) -> None:
    await async_setup_component(hass, "binary_sensor", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Entrée")

    entity_reg = er.async_get(hass)
    door = entity_reg.async_get_or_create("binary_sensor", "demo", "door")
    window = entity_reg.async_get_or_create("binary_sensor", "demo", "window")
    entity_reg.async_update_entity(door.entity_id, area_id=area.id)
    entity_reg.async_update_entity(window.entity_id, area_id=area.id)

    hass.states.async_set("binary_sensor.demo_door", "off", {"device_class": "door"})
    hass.states.async_set("binary_sensor.demo_window", "on", {"device_class": "window"})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.area_entree_openclose")
    assert state is not None
    assert state.state == "on"
