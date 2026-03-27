"""Fixtures for Auto Groups by Area tests."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.auto_groups_area.const import DOMAIN


@pytest.fixture
def make_config_entry():
    """Factory for config entries for the integration."""

    def _make(*, options: dict | None = None) -> MockConfigEntry:
        return MockConfigEntry(
            domain=DOMAIN, title="Auto Groups by Area", data={}, options=options or {}
        )

    return _make


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations) -> None:
    """Enable loading the integration from this repository's `custom_components/`."""
    # Fixture is provided by pytest-homeassistant-custom-component.
    return None


@pytest.fixture
async def setup_integration(hass: HomeAssistant, make_config_entry) -> MockConfigEntry:
    """Set up the integration."""
    # Ensure base platforms exist to avoid forward-setup failures.
    await async_setup_component(hass, "light", {})
    await async_setup_component(hass, "sensor", {})
    await async_setup_component(hass, "binary_sensor", {})

    config_entry = make_config_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
