# Auto Groups by Area
![License](https://img.shields.io/github/license/nico97118/auto_groups_area)
![Latest Release](https://img.shields.io/github/v/release/nico97118/auto_groups_area?include_prereleases)
![Repo Size](https://img.shields.io/github/repo-size/nico97118/auto_groups_area)

Custom component for Home Assistant that automatically creates and maintains groups of entities based on their assigned area.

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nico97118&repository=auto_groups_area&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=auto_groups_area)

## Features

- Automatically creates groups for each area (currently supports `light` entities)
- Groups are named `light.area_[area_name]` (e.g., `light.area_salon`)
- Optional area groups for `sensor` and `binary_sensor` by device class (temperature/humidity/illuminance, motion/presence/opening, door/window)
- Updates automatically when entities are added/removed from areas
- Updates automatically when areas are created/modified
- Initializes on Home Assistant startup
- Extensible architecture for future support of other entity domains

## Installation

### Manual Installation

1. Copy the folder `custom_components/auto_groups_area/` from this repository into your Home Assistant `custom_components` directory.

2. Restart Home Assistant

3. Add the integration from the UI:
   **Settings → Devices & services → Add integration → Auto Groups by Area**

### HACS Installation

1. Add this repository to HACS (custom repository, category **Integration**):
   - Use the badge/link at the top of this README, or
   - Manually add: `https://github.com/nico97118/auto_groups_area`

2. Install it from HACS, then restart Home Assistant

3. Add the integration from the UI:
   **Settings → Devices & services → Add integration → Auto Groups by Area**

## Usage

Once installed and configured, the component will:

1. **On startup**: Scan all areas and create groups for each area containing light entities
2. **Automatically**: Update groups when you:
   - Add a light to an area
   - Remove a light from an area
   - Move a light between areas
   - Create or modify areas

### Example

If you have an area named "Salon" with 3 lights:
- `light.plafonnier_salon`
- `light.lampe_1`
- `light.lampe_2`

The component will create:
- `light.area_salon` containing all 3 lights

You can then use this group in automations, scripts, or the UI:
```yaml
service: light.turn_on
target:
  entity_id: light.area_salon
data:
  brightness: 255
```

The group will automatically reflect:
- State: `on` if at least one light is on
- Brightness: Average of all lights
- Color: Average color of all lights
- And all other aggregated attributes

## Configuration

No configuration is required. Add the integration from the UI and it will create/update area groups automatically.

You can configure behavior from the UI:
**Settings → Devices & services → Auto Groups by Area → Options**

### Options

- **Create light groups / sensor groups / binary_sensor groups**: Enable or disable group creation by platform.
- **Entity id prefix (object id)**: Prefix used to build the entity_id (default: `area_`).
- **Create groups even when empty**: If disabled (default), empty groups are not created and existing groups are removed when they become empty.
- **Include entities whose device is assigned to the area**: Also include entities that inherit the area from their device assignment (recommended).
- **Only include these areas / Exclude these areas**: Multi-select of areas to include or exclude.
- **Binary Sensors**: Enable/disable each binary_sensor group type (motion/presence/opening/door-window).
- **Sensors**: Choose aggregation per sensor type (`max`, `mean`, `min`, `last`).
- **Advanced → Excluded entities**: Multi-select entities that will never be included in any group.

## Services

- `auto_groups_area.reload`: Force a full resynchronization of all area groups managed by this integration.

## Diagnostics

Home Assistant diagnostics are available for this integration (config entry and device diagnostics) from:
**Settings → Devices & services → Auto Groups by Area → Download diagnostics**.

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.auto_groups_area: debug
```

By default (`info`), logs are aggregated (sync summaries, group creation/removal, reload progress).
With `debug`, the integration becomes very verbose and includes per-area scans, membership diffs,
and registry event triggers.

Check the logs for messages like:
```
Sync light groups done (entry_id=..., areas_allowed=..., created=..., updated=..., removed=...)
Created light group for area 'Salon' with 3 member(s)
Area 'Salon' light scan (entry_id=..., scanned=..., members=..., ...)
Updating light group for area 'Salon' (..., added=[...], removed=[...])
```

## Future Enhancements

- [ ] Support for other entity domains (switch, fan, climate, etc.)
- [ ] Configuration options for customization
- [ ] Option to exclude certain areas
- [ ] Option to disable empty group creation
- [ ] Services to manually trigger group updates

## Contributing

Feel free to open issues or submit pull requests!

### Development

- QA / tests / lint / formatting: `TESTING.md`

## License

MIT License.
