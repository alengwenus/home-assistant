"""Support for LCN switches."""
import pypck

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_SWITCHES

from . import LcnDevice
from .const import CONF_CONNECTIONS, CONF_OUTPUT, DATA_LCN, OUTPUT_PORTS
from .helpers import get_connection


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up LCN switch platform from config_entry."""
    if "switches" not in config_entry.data:
        return

    devices = []
    host_name = config_entry.data[CONF_HOST]
    host = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]

    for config in config_entry.data[CONF_SWITCHES]:
        addr = pypck.lcn_addr.LcnAddr(*config[CONF_ADDRESS])
        address_connection = host.get_address_conn(addr)

        if config[CONF_OUTPUT] in OUTPUT_PORTS:
            device = LcnOutputSwitch(config, address_connection)
        else:  # in RELAY_PORTS
            device = LcnRelaySwitch(config, address_connection)

        devices.append(device)

    async_add_devices(devices)


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the LCN switch platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        if config[CONF_OUTPUT] in OUTPUT_PORTS:
            device = LcnOutputSwitch(config, address_connection)
        else:  # in RELAY_PORTS
            device = LcnRelaySwitch(config, address_connection)

        devices.append(device)

    async_add_entities(devices)


# async def async_will_remove_from_hass(hass, entry):
#     """Handle removal of LCN switch platform."""
#     pass


class LcnOutputSwitch(LcnDevice, SwitchEntity):
    """Representation of a LCN switch for output ports."""

    def __init__(self, config, address_connection):
        """Initialize the LCN switch."""
        super().__init__(config, address_connection)

        self.output = pypck.lcn_defs.OutputPort[config[CONF_OUTPUT]]

        self._is_on = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        super_unique_id = super().unique_id
        return super_unique_id + self.config[CONF_OUTPUT].lower()

    # @property
    # def device_info(self):
    #     """Return device specific attributes."""
    #     info = super().device_info
    #     model = f"{info['model']} ({self.config[CONF_OUTPUT].lower()})"
    #     info.update(model=model)
    #     return info

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


class LcnRelaySwitch(LcnDevice, SwitchEntity):
    """Representation of a LCN switch for relay ports."""

    def __init__(self, config, address_connection):
        """Initialize the LCN switch."""
        super().__init__(config, address_connection)

        self.output = pypck.lcn_defs.RelayPort[config[CONF_OUTPUT]]

        self._is_on = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        super_unique_id = super().unique_id
        return super_unique_id + self.config[CONF_OUTPUT].lower()

    @property
    def device_info(self):
        """Return device specific attributes."""
        info = super().device_info
        model = f"{info['model']} ({self.config[CONF_OUTPUT].lower()})"
        info.update(model=model)
        return info

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
