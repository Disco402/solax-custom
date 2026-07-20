import logging
from datetime import timedelta
import aiohttp

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfFrequency,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import DeviceInfo

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
DOMAIN = "solax"

def div10(val): return val / 10.0
def div100(val): return val / 100.0

def to_signed32(val):
    if val > 0x7FFFFFFF:
        return val - 0x100000000
    return val

DECODER_MAP = {
    "AC Voltage": (0, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, div10, True),
    "AC Output Current": (1, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, div10, True),
    "AC Output Power": (3, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, None, True),
    "PV1 Voltage": (4, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, div10, True),
    "PV2 Voltage": (5, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, div10, False),
    "PV1 Current": (8, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, div10, True),
    "PV2 Current": (9, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, div10, False),
    "PV1 Power": (13, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, None, True),
    "PV2 Power": (14, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, None, False),
    "AC Frequency": (2, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, div100, True),
    "Total Generated Energy": ((19, 20), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, div10, True),
    "Today's Generated Energy": (21, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, div10, True),
    "Exported Power": ((72, 73), UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, to_signed32, False),
    "Total Export Energy": ((74, 75), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, div100, False),
    "Total Import Energy": ((76, 77), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, div100, True),
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SolaX sensors from a UI config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    coordinator = SolaXDataCoordinator(hass, host, password)
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for sensor_name, config_data in DECODER_MAP.items():
        sensors.append(SolaXSensor(coordinator, entry, sensor_name, config_data))
    
    async_add_entities(sensors)


class SolaXDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the SolaX API."""

    def __init__(self, hass, host, password):
        self.url = f"http://{host}/"
        self.password = password
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch and parse data from the inverter."""
        payload = {
            "pwd": self.password,
            "optType": "ReadRealTimeData"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, data=payload, timeout=10) as response:
                    response.raise_for_status() 
                    json_response = await response.json(content_type=None)
                    
                    raw_data = json_response.get("Data", [])
                    if not raw_data:
                        raise UpdateFailed("No 'Data' array found in SolaX response.")

                    self.wifi_serial = json_response.get("sn", "Unknown")
                    self.firmware_version = json_response.get("ver", "Unknown")
                    self.inverter_type = json_response.get("type", "Unknown")
                    
                    info_data = json_response.get("Information", [])
                    if len(info_data) > 2:
                        self.inverter_serial = str(info_data[2]).strip()
                    else:
                        self.inverter_serial = self.wifi_serial

                    parsed_data = {}
                    for sensor_name, params in DECODER_MAP.items():
                        index_map = params[0]
                        modifier = params[4]
                        
                        try:
                            if isinstance(index_map, tuple):
                                low_idx, high_idx = index_map
                                val = raw_data[low_idx] + (raw_data[high_idx] << 16)
                            else:
                                val = raw_data[index_map]
                            
                            if modifier:
                                val = modifier(val)
                                
                            parsed_data[sensor_name] = val
                            
                        except IndexError:
                            _LOGGER.warning("Index missing in SolaX data for %s", sensor_name)
                            parsed_data[sensor_name] = None
                            
                    return parsed_data
                    
        except Exception as err:
            raise UpdateFailed(f"Error communicating with SolaX inverter: {err}")


class SolaXSensor(SensorEntity):
    """Representation of a SolaX Sensor."""

    def __init__(self, coordinator, entry, sensor_name, config_data):
        self.coordinator = coordinator
        self.entry = entry
        
        self._attr_name = f"SolaX {sensor_name}"
        self.data_key = sensor_name
        
        self._attr_native_unit_of_measurement = config_data[1]
        self._attr_device_class = config_data[2]
        self._attr_state_class = config_data[3]
        self._attr_entity_registry_enabled_default = config_data[5]
        
        self._attr_unique_id = f"solax_{entry.entry_id}_{sensor_name.replace(' ', '_').lower()}"

    @property
    def device_info(self):
        """Link this entity to a SolaX Device entry in Home Assistant."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.inverter_serial)},
            name="SolaX Inverter",
            manufacturer="SolaX Power",
            model=f"Type {self.coordinator.inverter_type}",
            sw_version=self.coordinator.firmware_version,
            serial_number=self.coordinator.inverter_serial,
        )

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self.data_key)
        return None

    @property
    def should_poll(self):
        return False

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )