"""Support for LCN switches."""
import pypck

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES, CONF_HOST

from .const import (
    CONF_CONNECTIONS,
    CONF_DOMAIN_DATA,
    CONF_OUTPUT,
    CONF_UNIQUE_DEVICE_ID,
    DATA_LCN,
    OUTPUT_PORTS,
)
from .helpers import get_device_address, get_device_config
from .lcn_entity import LcnEntity


def create_lcn_switch_entity(hass, entity_config, config_entry):
    """Set up an entity for this domain."""
    host_name = config_entry.data[CONF_HOST]
    host = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    device_config = get_device_config(
        entity_config[CONF_UNIQUE_DEVICE_ID], config_entry
    )
    addr = pypck.lcn_addr.LcnAddr(*get_device_address(device_config))
    device_connection = host.get_address_conn(addr)
    if entity_config[CONF_DOMAIN_DATA][CONF_OUTPUT] in OUTPUT_PORTS:
        entity = LcnOutputSwitch(entity_config, device_connection)
    else:  # in RELAY_PORTS
        entity = LcnRelaySwitch(entity_config, device_connection)
    return entity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LCN switch entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN:
            entities.append(create_lcn_switch_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnOutputSwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for output ports."""

    def __init__(self, config, address_connection):
        """Initialize the LCN switch."""
        super().__init__(config, address_connection)

        self.output = pypck.lcn_defs.OutputPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

        self._is_on = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(self.output)

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        await self.address_connection.cancel_status_request_handler(self.output)

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._is_on = True
        self.address_connection.dim_output(self.output.value, 100, 0)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._is_on = False
        self.address_connection.dim_output(self.output.value, 0, 0)
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set switch state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() != self.output.value
        ):
            return

        self._is_on = input_obj.get_percent() > 0
        self.async_write_ha_state()


class LcnRelaySwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for relay ports."""

    def __init__(self, config, address_connection):
        """Initialize the LCN switch."""
        super().__init__(config, address_connection)

        self.output = pypck.lcn_defs.RelayPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

        self._is_on = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(self.output)

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(self.output)

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._is_on = True

        states = [pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = pypck.lcn_defs.RelayStateModifier.ON
        self.address_connection.control_relays(states)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._is_on = False

        states = [pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = pypck.lcn_defs.RelayStateModifier.OFF
        self.address_connection.control_relays(states)
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set switch state when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        self._is_on = input_obj.get_state(self.output.value)
        self.async_write_ha_state()
