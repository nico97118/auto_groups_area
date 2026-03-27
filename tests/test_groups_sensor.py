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


async def test_sensor_humidity_group_created_when_state_appears_later(
    hass: HomeAssistant, setup_integration
) -> None:
    """Ensure sensor groups can be created when member states are restored later."""
    await async_setup_component(hass, "sensor", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    entity_reg = er.async_get(hass)
    hum = entity_reg.async_get_or_create("sensor", "demo", "hum")
    entity_reg.async_update_entity(hum.entity_id, area_id=area.id)

    # No initial state => should not create the group yet (default create_when_empty=False).
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.area_bureau_humidity") is None

    # Once the state appears, the coordinator should resync the area and create the group.
    hass.states.async_set(
        "sensor.demo_hum",
        "40",
        {"device_class": "humidity", "unit_of_measurement": "%"},
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.area_bureau_humidity")
    assert state is not None


@pytest.mark.usefixtures("setup_integration")
async def test_sensor_groups_use_registry_device_class_when_state_missing(
    hass: HomeAssistant,
) -> None:
    """Ensure groups are created even if member states are not yet available.

    Some integrations restore sensor states later during startup. We prefer the entity
    registry's stored device class (fallback to state) to avoid missing groups.
    """
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    entity_reg = er.async_get(hass)
    hum = entity_reg.async_get_or_create("sensor", "demo", "hum_no_state")
    lux = entity_reg.async_get_or_create("sensor", "demo", "lux_no_state")
    entity_reg.async_update_entity(
        hum.entity_id, area_id=area.id, original_device_class="humidity"
    )
    entity_reg.async_update_entity(
        lux.entity_id, area_id=area.id, original_device_class="illuminance"
    )

    # Intentionally do not set hass.states for these sensors.
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    hum_group = hass.states.get("sensor.area_bureau_humidity")
    lux_group = hass.states.get("sensor.area_bureau_illuminance")
    assert hum_group is not None
    assert lux_group is not None
    assert hum_group.attributes.get("device_class") == "humidity"
    assert lux_group.attributes.get("device_class") == "illuminance"
