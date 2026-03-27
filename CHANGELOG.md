# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

