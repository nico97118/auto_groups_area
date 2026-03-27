"""Fixtures for Auto Groups by Area tests."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.auto_groups_area.const import DOMAIN


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a config entry for the integration."""
    return MockConfigEntry(domain=DOMAIN, title="Auto Groups by Area", data={})


@pytest.fixture
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the integration."""
    # Ensure base platforms exist to avoid forward-setup failures.
    await async_setup_component(hass, "light", {})
    await async_setup_component(hass, "sensor", {})
    await async_setup_component(hass, "binary_sensor", {})

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
