"""Membership changes must propagate without the reload service."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.auto_groups_area.const import (
    CONF_ACTUATOR_DOMAINS,
    CONF_INCLUDE_DEVICE_AREA,
    DOMAIN,
)


@pytest.mark.parametrize(
    "domain,device_class",
    [
        ("light", None),
        ("switch", None),
        ("cover", None),
        ("sensor", "temperature"),
        ("binary_sensor", "motion"),
    ],
)
@pytest.mark.parametrize("inherit", [False, True])
async def test_live_entity_membership(
    hass, make_config_entry, domain, device_class, inherit
):
    """Create, move, reassign, disable, rename and delete through real registries."""
    areas = ar.async_get(hass)
    first = areas.async_create("First")
    second = areas.async_create("Second")
    config = make_config_entry(
        options={
            CONF_ACTUATOR_DOMAINS: ["light", "switch", "cover"],
            CONF_INCLUDE_DEVICE_AREA: inherit,
        }
    )
    config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()
    coordinators = hass.data[DOMAIN][config.entry_id]["coordinators"]
    coordinator = next(
        c for c in coordinators if c.__class__.__module__.endswith(f".{domain}")
    )
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    device1 = devices.async_get_or_create(
        config_entry_id=config.entry_id, identifiers={(DOMAIN, "first")}
    )
    device2 = devices.async_get_or_create(
        config_entry_id=config.entry_id, identifiers={(DOMAIN, "second")}
    )
    devices.async_update_device(device1.id, area_id=first.id)
    devices.async_update_device(device2.id, area_id=second.id)
    await hass.async_block_till_done()

    def memberships(entity_id):
        return {
            g._area_id
            for g in coordinator.groups.values()
            if entity_id in g._member_entity_ids
        }

    entity_id = f"{domain}.demo_member"
    attrs = {"device_class": device_class} if device_class else {}
    attrs.update({"supported_color_modes": ["onoff"]} if domain == "light" else {})
    entity = registry.async_get_or_create(
        domain, "demo", "member", device_id=device1.id
    )
    assert entity.entity_id == entity_id
    hass.states.async_set(entity_id, "20" if domain == "sensor" else "on", attrs)
    await hass.async_block_till_done()
    assert memberships(entity_id) == ({first.id} if inherit else set())

    registry.async_update_entity(entity_id, area_id=first.id, device_id=None)
    await hass.async_block_till_done()
    assert memberships(entity_id) == {first.id}
    registry.async_update_entity(entity_id, area_id=second.id)
    await hass.async_block_till_done()
    assert memberships(entity_id) == {second.id}
    registry.async_update_entity(entity_id, area_id=None, device_id=device1.id)
    await hass.async_block_till_done()
    assert memberships(entity_id) == ({first.id} if inherit else set())
    registry.async_update_entity(entity_id, device_id=device2.id)
    await hass.async_block_till_done()
    assert memberships(entity_id) == ({second.id} if inherit else set())

    registry.async_update_entity(entity_id, area_id=second.id, device_id=None)
    await hass.async_block_till_done()
    registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()
    assert not memberships(entity_id)
    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert memberships(entity_id) == {second.id}

    renamed = f"{domain}.renamed_member"
    registry.async_update_entity(entity_id, new_entity_id=renamed)
    hass.states.async_set(renamed, "20" if domain == "sensor" else "on", attrs)
    await hass.async_block_till_done()
    assert not memberships(entity_id)
    assert memberships(renamed) == {second.id}

    # A metadata burst must not queue any membership refresh.
    update = AsyncMock(wraps=coordinator._device_area_updates._update)
    coordinator._device_area_updates._update = update
    for i in range(100):
        registry.async_update_entity(renamed, name=f"Name {i}")
    await hass.async_block_till_done()
    update.assert_not_called()

    # Rapid moves preserve both old and final areas in one queued refresh.
    registry.async_update_entity(renamed, area_id=first.id)
    registry.async_update_entity(renamed, area_id=second.id)
    await hass.async_block_till_done()
    assert memberships(renamed) == {second.id}
    update.assert_awaited_once_with({first.id, second.id})
    update.reset_mock()

    registry.async_remove(renamed)
    await hass.async_block_till_done()
    assert not memberships(renamed)
    assert update.await_count == 1
