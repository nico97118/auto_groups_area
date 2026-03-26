# Auto Groups by Area

Custom component for Home Assistant that automatically creates and maintains groups of entities based on their assigned area.

## Features

- ✅ Automatically creates groups for each area (currently supports `light` entities)
- ✅ Groups are named `light.area_[area_name]` (e.g., `light.area_salon`)
- ✅ Optional area groups for `sensor` and `binary_sensor` by device class (temperature/humidity/illuminance, motion/presence/opening)
- ✅ Updates automatically when entities are added/removed from areas
- ✅ Updates automatically when areas are created/modified
- ✅ Initializes on Home Assistant startup
- ✅ Extensible architecture for future support of other entity domains

## Installation

### Manual Installation

1. Copy the `auto_groups_area` folder to your Home Assistant `custom_components` directory:
   ```
   custom_components/
   └── auto_groups_area/
       ├── __init__.py
       ├── config_flow.py
       ├── light.py
       ├── manifest.json
       └── const.py
   ```

3. Restart Home Assistant

### HACS Installation (future)

Coming soon!

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

Currently, the component works with default settings (lights only). Future versions will support:

```yaml
auto_groups_area:
  domains:
    - light
    - switch
    - fan
  create_empty_groups: true  # Create groups even for areas with no entities
  group_prefix: "area_"      # Customize the prefix
```

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
