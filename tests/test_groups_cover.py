from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import (
    CONF_ACTUATOR_DOMAINS,
    CONF_CREATE_WHEN_EMPTY,
    CONF_EXCLUDED_ENTITIES,
    DOMAIN,
)


async def _setup_cover_integration(hass: HomeAssistant, make_config_entry):
    await async_setup_component(hass, "cover", {})
    entry = make_config_entry(options={CONF_ACTUATOR_DOMAINS: ["cover"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("setup_integration")
async def test_cover_group_created_from_entity_area(
    hass: HomeAssistant, make_config_entry
) -> None:
    await _setup_cover_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Salon")

    entity_reg = er.async_get(hass)
    shutter = entity_reg.async_get_or_create("cover", "demo", "shutter")
    entity_reg.async_update_entity(shutter.entity_id, area_id=area.id)
    hass.states.async_set("cover.demo_shutter", "closed", {"supported_features": 0})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_salon")
    assert state is not None
    assert state.attributes["area_id"] == area.id
    assert "cover.demo_shutter" in state.attributes["entity_id"]


@pytest.mark.usefixtures("setup_integration")
async def test_cover_group_includes_device_area_when_enabled(
    hass: HomeAssistant, make_config_entry
) -> None:
    entry = await _setup_cover_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "dev1")}
    )
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("cover", "demo", "desk", device_id=device.id)
    hass.states.async_set("cover.demo_desk", "closed", {"supported_features": 0})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_bureau")
    assert state is not None
    assert "cover.demo_desk" in state.attributes["entity_id"]


async def test_cover_group_state_open_and_closed(
    hass: HomeAssistant, make_config_entry
) -> None:
    await _setup_cover_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Cuisine")

    entity_reg = er.async_get(hass)
    a = entity_reg.async_get_or_create("cover", "demo", "a")
    b = entity_reg.async_get_or_create("cover", "demo", "b")
    entity_reg.async_update_entity(a.entity_id, area_id=area.id)
    entity_reg.async_update_entity(b.entity_id, area_id=area.id)

    hass.states.async_set("cover.demo_a", "closed", {"supported_features": 0})
    hass.states.async_set("cover.demo_b", "open", {"supported_features": 0})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_cuisine")
    assert state is not None
    assert state.state == "open"

    hass.states.async_set("cover.demo_b", "closed", {"supported_features": 0})
    await hass.async_block_till_done()

    state2 = hass.states.get("cover.area_cuisine")
    assert state2 is not None
    assert state2.state == "closed"


async def test_cover_group_unknown_when_all_unknown_or_unavailable(
    hass: HomeAssistant, make_config_entry
) -> None:
    await _setup_cover_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Garage")

    entity_reg = er.async_get(hass)
    a = entity_reg.async_get_or_create("cover", "demo", "a")
    b = entity_reg.async_get_or_create("cover", "demo", "b")
    entity_reg.async_update_entity(a.entity_id, area_id=area.id)
    entity_reg.async_update_entity(b.entity_id, area_id=area.id)

    hass.states.async_set("cover.demo_a", "unknown", {"supported_features": 0})
    hass.states.async_set("cover.demo_b", "unavailable", {"supported_features": 0})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_garage")
    assert state is not None
    assert state.state == "unknown"


async def test_cover_group_excludes_entities(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "cover", {})
    entry = make_config_entry(
        options={
            CONF_ACTUATOR_DOMAINS: ["cover"],
            CONF_EXCLUDED_ENTITIES: ["cover.demo_skip"],
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Couloir")

    entity_reg = er.async_get(hass)
    skip = entity_reg.async_get_or_create("cover", "demo", "skip")
    ok = entity_reg.async_get_or_create("cover", "demo", "ok")
    entity_reg.async_update_entity(skip.entity_id, area_id=area.id)
    entity_reg.async_update_entity(ok.entity_id, area_id=area.id)

    hass.states.async_set("cover.demo_skip", "open", {"supported_features": 0})
    hass.states.async_set("cover.demo_ok", "open", {"supported_features": 0})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_couloir")
    assert state is not None
    assert "cover.demo_ok" in state.attributes["entity_id"]
    assert "cover.demo_skip" not in state.attributes["entity_id"]


async def test_cover_no_empty_group_by_default(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "cover", {})
    entry = make_config_entry(options={CONF_ACTUATOR_DOMAINS: ["cover"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area_reg.async_create("EmptyArea")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get("cover.area_emptyarea") is None


async def test_cover_create_when_empty(hass: HomeAssistant, make_config_entry) -> None:
    await async_setup_component(hass, "cover", {})
    entry = make_config_entry(
        options={
            CONF_ACTUATOR_DOMAINS: ["cover"],
            CONF_CREATE_WHEN_EMPTY: True,
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area_reg.async_create("EmptyArea2")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_emptyarea2")
    assert state is not None
    assert state.state == "unknown"


async def test_cover_supported_features_is_intersection(
    hass: HomeAssistant, make_config_entry
) -> None:
    await _setup_cover_integration(hass, make_config_entry)

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Chambre")

    entity_reg = er.async_get(hass)
    a = entity_reg.async_get_or_create("cover", "demo", "a")
    b = entity_reg.async_get_or_create("cover", "demo", "b")
    entity_reg.async_update_entity(a.entity_id, area_id=area.id)
    entity_reg.async_update_entity(b.entity_id, area_id=area.id)

    hass.states.async_set("cover.demo_a", "open", {"supported_features": 7})
    hass.states.async_set("cover.demo_b", "open", {"supported_features": 3})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.area_chambre")
    assert state is not None
    assert state.attributes.get("supported_features") == (7 & 3)
