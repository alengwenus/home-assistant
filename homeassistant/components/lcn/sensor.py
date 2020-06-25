"""Support for LCN sensors."""
import pypck

from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_UNIT_OF_MEASUREMENT,
)

from .const import (
    CONF_CONNECTIONS,
    CONF_DOMAIN_DATA,
    CONF_SOURCE,
    CONF_UNIQUE_DEVICE_ID,
    DATA_LCN,
    LED_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VARIABLES,
)
from .helpers import get_device_address, get_device_config
from .lcn_entity import LcnEntity


def create_lcn_sensor_entity(hass, entity_config, config_entry):
    """Set up an entity for this domain."""
    host_name = config_entry.data[CONF_HOST]
    host = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    device_config = get_device_config(
        entity_config[CONF_UNIQUE_DEVICE_ID], config_entry
    )
    addr = pypck.lcn_addr.LcnAddr(*get_device_address(device_config))
    device_connection = host.get_address_conn(addr)

    if (
        entity_config[CONF_DOMAIN_DATA][CONF_SOURCE]
        in VARIABLES + SETPOINTS + THRESHOLDS + S0_INPUTS
    ):
        entity = LcnVariableSensor(entity_config, device_connection)
    else:  # in LED_PORTS + LOGICOP_PORTS
        entity = LcnLedLogicSensor(entity_config, device_connection)
    return entity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LCN switch entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_SENSOR:
            entities.append(create_lcn_sensor_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnVariableSensor(LcnEntity):
    """Representation of a LCN sensor for variables."""

    def __init__(self, config, address_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, address_connection)

        self.variable = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        self.unit = pypck.lcn_defs.VarUnit.parse(
            config[CONF_DOMAIN_DATA][CONF_UNIT_OF_MEASUREMENT]
        )

        self._value = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(self.variable)

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(self.variable)

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.unit.value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.variable
        ):
            return

        self._value = input_obj.get_value().to_var_unit(self.unit)
        self.async_write_ha_state()


class LcnLedLogicSensor(LcnEntity):
    """Representation of a LCN sensor for leds and logicops."""

    def __init__(self, config, address_connection):
        """Initialize the LCN sensor."""
        super().__init__(config, address_connection)

        if config[CONF_DOMAIN_DATA][CONF_SOURCE] in LED_PORTS:
            self.source = pypck.lcn_defs.LedPort[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        else:
            self.source = pypck.lcn_defs.LogicOpPort[
                config[CONF_DOMAIN_DATA][CONF_SOURCE]
            ]

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
    def state(self):
        """Return the state of the entity."""
        return self._value

    def input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusLedsAndLogicOps):
            return

        if self.source in pypck.lcn_defs.LedPort:
            self._value = input_obj.get_led_state(self.source.value).name.lower()
        elif self.source in pypck.lcn_defs.LogicOpPort:
            self._value = input_obj.get_logic_op_state(self.source.value).name.lower()

        self.async_write_ha_state()
