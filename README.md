# Auto Groups by Area

Custom component for Home Assistant that automatically creates and maintains groups of entities based on their assigned area.

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

1. Copy `custom_components/auto_groups_area/` from this repository into your Home Assistant `custom_components` directory:
   ```
   custom_components/
   └── auto_groups_area/
       ├── __init__.py
       ├── config_flow.py
       ├── binary_sensor.py
       ├── light.py
       ├── manifest.json
       ├── sensor.py
       ├── strings.json
       └── const.py
   ```

2. Restart Home Assistant

3. Add the integration from the UI:
   **Settings → Devices & services → Add integration → Auto Groups by Area**

### HACS Installation

1. In HACS, add this GitHub repository as a **Custom repository** (category: **Integration**)

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

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.auto_groups_area: debug
```

Check the logs for messages like:
```
Area 'Salon' (area_id): found 3 light entities
Creating/updating group light.area_salon with 3 entities
```

## Future Enhancements

- [ ] Support for other entity domains (switch, fan, climate, etc.)
- [ ] Configuration options for customization
- [ ] Option to exclude certain areas
- [ ] Option to disable empty group creation
- [ ] Services to manually trigger group updates

## Contributing

Feel free to open issues or submit pull requests!

## License

MIT
