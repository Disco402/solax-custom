# SolaX Local

A Home Assistant integration for local polling of SolaX inverters.

## Features

- Polls inverter data every 10 seconds
- Provides power, voltage, current, energy, and frequency sensors
- Default-disabled sensors: PV2 and exported values
- Local polling integration with support for config flow

## Installation

1. Copy the `custom_components/solax_local` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration**.
4. Search for `SolaX Local` and enter the inverter host IP and password.

## Configuration

- `Host`: IP address or hostname of the SolaX inverter
- `Password`: API password used by the inverter

## Sensor defaults

The integration exposes sensors for inverter values. By default, the following are disabled in the entity registry:

- `PV2 Voltage`
- `PV2 Current`
- `PV2 Power`
- `Exported Power`
- `Total Export Energy`

You can enable them later from Home Assistant's entity settings.