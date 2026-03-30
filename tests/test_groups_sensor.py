from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import (
    AGGREGATION_LAST,
    AGGREGATION_MAX,
    AGGREGATION_MEAN,
    CONF_HUMIDITY_AGGREGATION,
    CONF_ILLUMINANCE_AGGREGATION,
    DOMAIN,
)


async def _setup_area_with_sensors(hass: HomeAssistant, area_name: str) -> str:
    area_reg = ar.async_get(hass)
    area = area_reg.async_create(area_name)

    entity_reg = er.async_get(hass)
    t1 = entity_reg.async_get_or_create("sensor", "demo", "t1")
    t2 = entity_reg.async_get_or_create("sensor", "demo", "t2")
    entity_reg.async_update_entity(t1.entity_id, area_id=area.id)
    entity_reg.async_update_entity(t2.entity_id, area_id=area.id)

    hass.states.async_set(
        "sensor.demo_t1",
        "20",
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )
    hass.states.async_set(
        "sensor.demo_t2",
        "22",
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )

    return area.id


async def test_sensor_temperature_mean(hass: HomeAssistant, make_config_entry) -> None:
    await async_setup_component(hass, "sensor", {})

    entry = make_config_entry(options={CONF_HUMIDITY_AGGREGATION: AGGREGATION_MEAN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _setup_area_with_sensors(hass, "Salon")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.area_salon_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(21.0)


async def test_sensor_illuminance_max(hass: HomeAssistant, make_config_entry) -> None:
    await async_setup_component(hass, "sensor", {})

    entry = make_config_entry(options={CONF_ILLUMINANCE_AGGREGATION: AGGREGATION_MAX})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    entity_reg = er.async_get(hass)
    lux1 = entity_reg.async_get_or_create("sensor", "demo", "lux1")
    lux2 = entity_reg.async_get_or_create("sensor", "demo", "lux2")
    entity_reg.async_update_entity(lux1.entity_id, area_id=area.id)
    entity_reg.async_update_entity(lux2.entity_id, area_id=area.id)

    hass.states.async_set(
        "sensor.demo_lux1",
        "100",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )
    hass.states.async_set(
        "sensor.demo_lux2",
        "250",
        {"device_class": "illuminance", "unit_of_measurement": "lx"},
    )

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.area_bureau_illuminance")
    assert state is not None
    assert float(state.state) == 250.0


async def test_sensor_last_uses_latest_changed(
    hass: HomeAssistant, make_config_entry
) -> None:
    await async_setup_component(hass, "sensor", {})

    entry = make_config_entry(options={CONF_HUMIDITY_AGGREGATION: AGGREGATION_LAST})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Salle de bain")

    entity_reg = er.async_get(hass)
    h1 = entity_reg.async_get_or_create("sensor", "demo", "h1")
    h2 = entity_reg.async_get_or_create("sensor", "demo", "h2")
    entity_reg.async_update_entity(h1.entity_id, area_id=area.id)
    entity_reg.async_update_entity(h2.entity_id, area_id=area.id)

    hass.states.async_set(
        "sensor.demo_h1", "40", {"device_class": "humidity", "unit_of_measurement": "%"}
    )
    hass.states.async_set(
        "sensor.demo_h2", "45", {"device_class": "humidity", "unit_of_measurement": "%"}
    )

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    group = hass.states.get("sensor.area_salle_de_bain_humidity")
    assert group is not None

    # Update h1 to be the most recently changed -> group should follow.
    hass.states.async_set(
        "sensor.demo_h1", "55", {"device_class": "humidity", "unit_of_measurement": "%"}
    )
    await hass.async_block_till_done()

    group2 = hass.states.get("sensor.area_salle_de_bain_humidity")
    assert group2 is not None
    assert float(group2.state) == 55.0


async def test_sensor_group_ignores_self_included_entity(
    hass: HomeAssistant, make_config_entry, caplog
) -> None:
    await async_setup_component(hass, "sensor", {})

    entry = make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("SelfIncludeSensor")

    entity_reg = er.async_get(hass)

    # Real sensor member (temperature)
    t1 = entity_reg.async_get_or_create("sensor", "demo", "t_self")
    entity_reg.async_update_entity(t1.entity_id, area_id=area.id)
    hass.states.async_set(
        t1.entity_id,
        "21",
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )

    # Fake dynamic sensor group assigned to same area
    group_unique_id = f"{DOMAIN}_sensor_temperature_{area.id}"
    fake_group = entity_reg.async_get_or_create("sensor", DOMAIN, group_unique_id)
    entity_reg.async_update_entity(fake_group.entity_id, area_id=area.id)
    # Make the fake group look like a temperature sensor so it would normally
    # be picked up by the area scan (to test filtering).
    hass.states.async_set(
        fake_group.entity_id,
        "0",
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )

    caplog.clear()
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    # Find created group entry by unique_id
    reg = None
    for entry in entity_reg.entities.values():
        if getattr(entry, "unique_id", None) == group_unique_id:
            reg = entry
            break
    assert reg is not None
    state = hass.states.get(reg.entity_id)
    assert state is not None
    assert fake_group.entity_id not in state.attributes.get("entity_id", [])
    assert any("Skipping self-include" in rec.getMessage() for rec in caplog.records)
