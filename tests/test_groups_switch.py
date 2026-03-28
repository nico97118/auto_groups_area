from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import (
    CONF_ENABLE_SWITCHES,
    CONF_EXCLUDED_ENTITIES,
    CONF_INCLUDE_DEVICE_AREA,
    DOMAIN,
)


async def _setup_switch_integration(hass: HomeAssistant, make_config_entry):
    await async_setup_component(hass, "switch", {})
    entry = make_config_entry(options={CONF_ENABLE_SWITCHES: True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("setup_integration")
async def test_switch_group_created_from_entity_area(
    hass: HomeAssistant, make_config_entry
) -> None:
    await _setup_switch_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Salon")

    entity_reg = er.async_get(hass)
    plug = entity_reg.async_get_or_create("switch", "demo", "plug")
    entity_reg.async_update_entity(plug.entity_id, area_id=area.id)
    hass.states.async_set("switch.demo_plug", "on")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("switch.area_salon")
    assert state is not None
    assert state.attributes["area_id"] == area.id
    assert "switch.demo_plug" in state.attributes["entity_id"]


@pytest.mark.usefixtures("setup_integration")
async def test_switch_group_includes_device_area_when_enabled(
    hass: HomeAssistant, make_config_entry
) -> None:
    entry = await _setup_switch_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "dev1")}
    )
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("switch", "demo", "desk", device_id=device.id)
    hass.states.async_set("switch.demo_desk", "on")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("switch.area_bureau")
    assert state is not None
    assert "switch.demo_desk" in state.attributes["entity_id"]


async def test_switch_group_excludes_entities(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "switch", {})
    entry = make_config_entry(
        options={
            CONF_ENABLE_SWITCHES: True,
            CONF_EXCLUDED_ENTITIES: ["switch.demo_skip"],
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Cuisine")

    entity_reg = er.async_get(hass)
    skip = entity_reg.async_get_or_create("switch", "demo", "skip")
    ok = entity_reg.async_get_or_create("switch", "demo", "ok")
    entity_reg.async_update_entity(skip.entity_id, area_id=area.id)
    entity_reg.async_update_entity(ok.entity_id, area_id=area.id)

    hass.states.async_set("switch.demo_skip", "on")
    hass.states.async_set("switch.demo_ok", "on")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("switch.area_cuisine")
    assert state is not None
    assert "switch.demo_ok" in state.attributes["entity_id"]
    assert "switch.demo_skip" not in state.attributes["entity_id"]


async def test_switch_include_device_area_toggle(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "switch", {})
    entry = make_config_entry(
        options={
            CONF_ENABLE_SWITCHES: True,
            CONF_INCLUDE_DEVICE_AREA: False,
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Garage")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "dev2")}
    )
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("switch", "demo", "car", device_id=device.id)
    hass.states.async_set("switch.demo_car", "on")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get("switch.area_garage") is None
