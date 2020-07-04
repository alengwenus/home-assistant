"""Support for LCN binary sensors."""
import pypck

from homeassistant.components.binary_sensor import (
    DOMAIN as DOMAIN_BINARY_SENSOR,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES

from .const import (
    ADD_ENTITIES_CALLBACKS,
    BINSENSOR_PORTS,
    CONF_DOMAIN_DATA,
    CONF_SOURCE,
    CONF_UNIQUE_DEVICE_ID,
    DOMAIN as DOMAIN_LCN,
    SETPOINTS,
)
from .helpers import get_device_connection
from .lcn_entity import LcnEntity


def create_lcn_binary_sensor_entity(hass, entity_config, config_entry):
    """Set up an entity for this domain."""
    host_name = config_entry.entry_id
    device_connection = get_device_connection(
        hass, entity_config[CONF_UNIQUE_DEVICE_ID], config_entry
    )

    if entity_config[CONF_DOMAIN_DATA][CONF_SOURCE] in SETPOINTS:
        entity = LcnRegulatorLockSensor(entity_config, host_name, device_connection)
    elif entity_config[CONF_DOMAIN_DATA][CONF_SOURCE] in BINSENSOR_PORTS:
        entity = LcnBinarySensor(entity_config, host_name, device_connection)
    else:  # in KEY
        entity = LcnLockKeysSensor(entity_config, host_name, device_connection)
    return entity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LCN switch entities from a config entry."""
    callbacks = hass.data[DOMAIN_LCN][config_entry.entry_id][ADD_ENTITIES_CALLBACKS]
    callbacks[DOMAIN_BINARY_SENSOR] = (
        async_add_entities,
        create_lcn_binary_sensor_entity,
    )

    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_BINARY_SENSOR:
            entities.append(
                create_lcn_binary_sensor_entity(hass, entity_config, config_entry)
            )

    async_add_entities(entities)


class LcnRegulatorLockSensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN binary sensor for regulator locks."""

    def __init__(self, config, host_id, address_connection):
        """Initialize the LCN binary sensor."""
        super().__init__(config, host_id, address_connection)

        self.setpoint_variable = pypck.lcn_defs.Var[
            config[CONF_DOMAIN_DATA][CONF_SOURCE]
        ]

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(
                self.setpoint_variable
            )

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(
                self.setpoint_variable
            )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.setpoint_variable
        ):
            return

        self._value = input_obj.get_value().is_locked_regulator()
        self.async_write_ha_state()


class LcnBinarySensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN binary sensor for binary sensor ports."""

    def __init__(self, config, host_id, address_connection):
        """Initialize the LCN binary sensor."""
        super().__init__(config, host_id, address_connection)

        self.bin_sensor_port = pypck.lcn_defs.BinSensorPort[
            config[CONF_DOMAIN_DATA][CONF_SOURCE]
        ]

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(
                self.bin_sensor_port
            )

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(
                self.bin_sensor_port
            )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusBinSensors):
            return

        self._value = input_obj.get_state(self.bin_sensor_port.value)
        self.async_write_ha_state()


class LcnLockKeysSensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN sensor for key locks."""

    def __init__(self, config, host_id, address_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, host_id, address_connection)

        self.source = pypck.lcn_defs.Key[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(self.source)

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(self.source)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusKeyLocks)
            or self.source not in pypck.lcn_defs.Key
        ):
            return

        table_id = ord(self.source.name[0]) - 65
        key_id = int(self.source.name[1]) - 1

        self._value = input_obj.get_state(table_id, key_id)
        self.async_write_ha_state()
