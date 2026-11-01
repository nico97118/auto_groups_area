"""Generated groups must not feed back into area membership."""

import pytest
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

from custom_components.auto_groups_area.const import CONF_ACTUATOR_DOMAINS, DOMAIN


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
async def test_generated_groups_excluded(hass, make_config_entry, domain, device_class):
    area = ar.async_get(hass).async_create("Room")
    registry = er.async_get(hass)
    member = registry.async_get_or_create(domain, "demo", "member")
    generated = registry.async_get_or_create(domain, DOMAIN, "another_generated_group")
    attrs = {"device_class": device_class} if device_class else {}
    for entity in (member, generated):
        registry.async_update_entity(entity.entity_id, area_id=area.id)
        hass.states.async_set(
            entity.entity_id, "20" if domain == "sensor" else "on", attrs
        )
    config = make_config_entry(
        options={CONF_ACTUATOR_DOMAINS: ["light", "switch", "cover"]}
    )
    config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()
    coordinator = next(
        c
        for c in hass.data[DOMAIN][config.entry_id]["coordinators"]
        if c.__class__.__module__.endswith(f".{domain}")
    )
    assert coordinator.groups
    for group in coordinator.groups.values():
        assert generated.entity_id not in group._member_entity_ids
    assert any(
        member.entity_id in group._member_entity_ids
        for group in coordinator.groups.values()
    )
