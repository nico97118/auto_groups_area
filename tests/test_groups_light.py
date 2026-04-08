from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import (
    CONF_CREATE_WHEN_EMPTY,
    CONF_EXCLUDED_ENTITIES,
    CONF_INCLUDE_DEVICE_AREA,
    DOMAIN,
)


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_created_from_entity_area(hass: HomeAssistant) -> None:
    await async_setup_component(hass, "light", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Salon")

    entity_reg = er.async_get(hass)
    lamp = entity_reg.async_get_or_create("light", "demo", "lamp")
    entity_reg.async_update_entity(lamp.entity_id, area_id=area.id)
    hass.states.async_set("light.demo_lamp", "on", {"supported_color_modes": ["onoff"]})

    # Trigger a reload to build groups.
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_salon")
    assert state is not None
    assert state.attributes["area_id"] == area.id
    assert "light.demo_lamp" in state.attributes["entity_id"]


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_includes_device_area_when_enabled(
    hass: HomeAssistant, setup_integration
) -> None:
    await async_setup_component(hass, "light", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=setup_integration.entry_id, identifiers={("demo", "dev1")}
    )
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "desk", device_id=device.id)
    hass.states.async_set("light.demo_desk", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_bureau")
    assert state is not None
    assert "light.demo_desk" in state.attributes["entity_id"]


async def test_light_group_excludes_entities(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "light", {})

    entry = make_config_entry(options={CONF_EXCLUDED_ENTITIES: ["light.demo_skip"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Cuisine")

    entity_reg = er.async_get(hass)
    skip = entity_reg.async_get_or_create("light", "demo", "skip")
    ok = entity_reg.async_get_or_create("light", "demo", "ok")
    entity_reg.async_update_entity(skip.entity_id, area_id=area.id)
    entity_reg.async_update_entity(ok.entity_id, area_id=area.id)

    hass.states.async_set("light.demo_skip", "on", {"supported_color_modes": ["onoff"]})
    hass.states.async_set("light.demo_ok", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_cuisine")
    assert state is not None
    assert "light.demo_ok" in state.attributes["entity_id"]
    assert "light.demo_skip" not in state.attributes["entity_id"]


async def test_light_no_empty_group_by_default(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "light", {})

    entry = make_config_entry(options={CONF_CREATE_WHEN_EMPTY: False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area_reg.async_create("EmptyArea")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get("light.area_emptyarea") is None


async def test_light_include_device_area_toggle(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "light", {})

    entry = make_config_entry(options={CONF_INCLUDE_DEVICE_AREA: False})
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
    entity_reg.async_get_or_create("light", "demo", "car", device_id=device.id)
    hass.states.async_set("light.demo_car", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    # Should NOT create group because entity isn't directly assigned to area and include_device_area is disabled.
    assert hass.states.get("light.area_garage") is None


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_color_mode_is_supported(hass: HomeAssistant) -> None:
    """Ensure group color_mode never violates supported_color_modes.

    This can happen with mixed member lights where a dimmable-only light reports
    ColorMode.BRIGHTNESS while the group exposes only RGB/COLOR_TEMP modes.
    """
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    entity_reg = er.async_get(hass)
    dim = entity_reg.async_get_or_create("light", "demo", "dim")
    rgb = entity_reg.async_get_or_create("light", "demo", "rgb")
    entity_reg.async_update_entity(dim.entity_id, area_id=area.id)
    entity_reg.async_update_entity(rgb.entity_id, area_id=area.id)

    hass.states.async_set(
        "light.demo_dim",
        "on",
        {
            "supported_color_modes": ["brightness"],
            "color_mode": "brightness",
            "brightness": 128,
        },
    )
    hass.states.async_set(
        "light.demo_rgb",
        "off",
        {"supported_color_modes": ["rgb", "color_temp"], "color_mode": "rgb"},
    )

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_bureau")
    assert state is not None

    supported = state.attributes.get("supported_color_modes")
    assert isinstance(supported, (list, tuple, set))
    assert state.attributes.get("color_mode") in set(supported)


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_prefers_xy_color_over_color_temp(
    hass: HomeAssistant,
) -> None:
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Chambre")

    entity_reg = er.async_get(hass)
    lamp = entity_reg.async_get_or_create("light", "demo", "xy")
    entity_reg.async_update_entity(lamp.entity_id, area_id=area.id)

    hass.states.async_set(
        lamp.entity_id,
        "off",
        {"supported_color_modes": ["xy", "color_temp"], "color_mode": "xy"},
    )

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_chambre")
    assert state is not None
    supported = set(state.attributes.get("supported_color_modes", []))
    assert "xy" in supported


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_ignores_self_included_entity(
    hass: HomeAssistant, caplog
) -> None:
    """Ensure a dynamic group entity assigned to its own area is ignored."""
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("SelfInclude")

    entity_reg = er.async_get(hass)

    # Normal member light
    lamp = entity_reg.async_get_or_create("light", "demo", "lamp_self")
    entity_reg.async_update_entity(lamp.entity_id, area_id=area.id)
    hass.states.async_set(lamp.entity_id, "on", {"supported_color_modes": ["onoff"]})

    # Simulate the dynamic group entity being present in the registry and assigned
    # to the same area (same unique_id as the group would have).
    group_unique_id = f"{DOMAIN}_light_{area.id}"
    fake_group = entity_reg.async_get_or_create("light", DOMAIN, group_unique_id)
    entity_reg.async_update_entity(fake_group.entity_id, area_id=area.id)
    hass.states.async_set(fake_group.entity_id, "off")

    caplog.clear()
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    # The created group entity may not have the exact expected entity_id
    # (registry entries can influence the final id). Find it by unique_id.
    reg = None
    for entry in entity_reg.entities.values():
        if getattr(entry, "unique_id", None) == group_unique_id:
            reg = entry
            break
    assert reg is not None
    state = hass.states.get(reg.entity_id)
    assert state is not None
    # The fake group entity must NOT be included as a member
    assert fake_group.entity_id not in state.attributes.get("entity_id", [])
    # And we should have logged a warning about skipping self-include
    assert any("Skipping self-include" in rec.getMessage() for rec in caplog.records)
