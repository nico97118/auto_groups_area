# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Verbose debug logging for group sync/update triggers (per-area/per-group scan details, membership diffs).
### Changed
- `auto_groups_area.reload` now logs aggregated progress and any per-entry errors instead of failing hard on the first exception.
### Fixed
- Sensor and binary_sensor group membership now prefers device class from the entity registry (fallback to state) to avoid missing groups during startup when states are not yet available.

## [0.8.0-beta.1] - 2026-03-27
### Added
- Ruff configuration (`pyproject.toml`) and optional lint dependencies (`requirements_lint.txt`).
- GitHub Actions lint workflow running `ruff check` + `ruff format --check` (`.github/workflows/lint.yml`).
- Optional `pre-commit` hook configuration to auto-run Ruff on commit (`.pre-commit-config.yaml`).
- Test folder README for nicer GitHub browsing (`tests/README.md`) and a development link from the main `README.md`.
### Fixed
- Area light group `color_mode` is guaranteed to be within `supported_color_modes` to satisfy Home Assistant validation (plus a regression test).

## [0.0.7-alpha.2] - 2026-03-27
### Added
- GitHub Actions test workflow and local testing documentation.
- Pytest-based test suite (via `pytest-homeassistant-custom-component`).
### Fixed
- Light group color mode reporting to satisfy Home Assistant validation.
- Group creation/registry edge cases uncovered by tests.

## [0.0.7-alpha.1] - 2026-03-27
### Added
- Home Assistant diagnostics support (config entry and device diagnostics).

## [0.0.6-alpha.1] - 2026-03-27
### Added
- `auto_groups_area.reload` service to force a full resynchronization of all groups.
- `services.yaml` documentation for the service.

## [0.0.5-alpha] - 2026-03-27
### Added
- HACS-friendly repository layout (`custom_components/auto_groups_area`) and `hacs.json`.
- Area-based groups for `light`, `sensor`, and `binary_sensor` (including entities inheriting area via device assignment).
- Aggregated sensor groups (temperature/humidity/illuminance) with configurable aggregation (`mean`, `max`, `min`, `last`).
- Binary sensor groups for motion, presence, opening, and door/window open-close.
- UI configuration (Options Flow) with multi-step options, area include/exclude, and excluded entities.
- Integration icon (`icon.png`).
