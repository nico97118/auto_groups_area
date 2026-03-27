# Testing (QA Plan)

This repository uses `pytest` + `pytest-homeassistant-custom-component` to validate the integration behavior in a mocked Home Assistant instance (no real HA install required).

## Scope

### Critical paths
- Config entry setup/unload
- Config flow + options flow (multi-step)
- Group creation/removal rules:
  - entity assigned to area
  - entity inheriting area via device assignment
  - include/exclude areas
  - excluded entities never included
  - empty group behavior (`create_when_empty`)
- Aggregations for sensors (`mean`, `max`, `min`, `last`)
- Manual service: `auto_groups_area.reload`
- Diagnostics endpoints (config entry + device)

## What is covered by automated tests

Tests live under `tests/`:
- `tests/test_config_flow.py`: config flow creation + single-instance enforcement.
- `tests/test_options_flow.py`: options flow multi-step logic + stored options.
- `tests/test_groups_light.py`: light groups by area/device + exclusions/toggles.
- `tests/test_groups_sensor.py`: sensor groups and aggregation modes.
- `tests/test_groups_binary_sensor.py`: binary_sensor `openclose` behavior.
- `tests/test_service_reload.py`: reload service creates groups after changes.
- `tests/test_diagnostics.py`: diagnostics endpoints return expected structure.

## Running tests locally

Home Assistant does not support all Python versions. Use a supported Python version (typically Python 3.12).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
python -m pytest
```

## CI

GitHub Actions runs `pytest` on every push and pull request via `.github/workflows/tests.yml`.
