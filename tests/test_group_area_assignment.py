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


async def test_area_assignment_option_lifecycle(hass, make_config_entry):
    """Opt in applies to existing/new groups; opt out and reload preserve choices."""
    from custom_components.auto_groups_area.const import CONF_ASSIGN_GROUP_AREA

    areas = ar.async_get(hass)
    room = areas.async_create("Room")
    manual = areas.async_create("Manual")
    registry = er.async_get(hass)
    domains = {
        "light": None,
        "switch": None,
        "cover": None,
        "sensor": "temperature",
        "binary_sensor": "motion",
    }
    for domain, device_class in domains.items():
        member = registry.async_get_or_create(domain, "demo", "member")
        registry.async_update_entity(member.entity_id, area_id=room.id)
        attrs = {"device_class": device_class} if device_class else {}
        hass.states.async_set(
            member.entity_id, "20" if domain == "sensor" else "on", attrs
        )
    config = make_config_entry(
        options={CONF_ACTUATOR_DOMAINS: ["light", "switch", "cover"]}
    )
    config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    def groups():
        return [
            e
            for e in registry.entities.values()
            if e.platform == DOMAIN and e.config_entry_id == config.entry_id
        ]

    assert len(groups()) == 5
    assert all(e.area_id is None for e in groups())
    manually_assigned = next(e for e in groups() if e.domain == "light")
    registry.async_update_entity(manually_assigned.entity_id, area_id=manual.id)
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        config, options={**config.options, CONF_ASSIGN_GROUP_AREA: True}
    )
    await hass.async_block_till_done()
    for entry in groups():
        assert entry.area_id == (
            manual.id if entry.entity_id == manually_assigned.entity_id else room.id
        )

    # Adding a new area/member while enabled also assigns its generated group.
    new_area = areas.async_create("New")
    member = registry.async_get_or_create("light", "demo", "new_member")
    registry.async_update_entity(member.entity_id, area_id=new_area.id)
    hass.states.async_set(member.entity_id, "on")
    await hass.async_block_till_done()
    new_group = next(
        e for e in groups() if e.unique_id == f"{DOMAIN}_light_{new_area.id}"
    )
    assert new_group.area_id == new_area.id

    # Repeated refreshes must neither write areas again nor include generated groups.
    from unittest.mock import patch

    with patch.object(
        registry, "async_update_entity", wraps=registry.async_update_entity
    ) as update:
        for _ in range(3):
            await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
            await hass.async_block_till_done()
        assert not [call for call in update.call_args_list if "area_id" in call.kwargs]
    generated_ids = {e.entity_id for e in groups()}
    for coordinator in hass.data[DOMAIN][config.entry_id]["coordinators"]:
        for group in coordinator.groups.values():
            assert generated_ids.isdisjoint(group._member_entity_ids)

    await hass.config_entries.async_reload(config.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(manually_assigned.entity_id).area_id == manual.id
    hass.config_entries.async_update_entry(
        config, options={**config.options, CONF_ASSIGN_GROUP_AREA: False}
    )
    await hass.async_block_till_done()
    assert registry.async_get(new_group.entity_id).area_id == new_area.id
    registry.async_update_entity(new_group.entity_id, area_id=None)
    await hass.config_entries.async_reload(config.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(new_group.entity_id).area_id is None
