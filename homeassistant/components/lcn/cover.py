"""Support for LCN covers."""
import pypck

from homeassistant.components.cover import DOMAIN as DOMAIN_COVER, CoverEntity
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES

from .const import (
    CONF_DOMAIN_DATA,
    CONF_MOTOR,
    CONF_REVERSE_TIME,
    CONF_UNIQUE_DEVICE_ID,
)
from .helpers import get_device_connection
from .lcn_entity import LcnEntity


def create_lcn_cover_entity(hass, entity_config, config_entry):
    """Set up an entity for this domain."""
    host_name = config_entry.entry_id
    device_connection = get_device_connection(
        hass, entity_config[CONF_UNIQUE_DEVICE_ID], config_entry
    )

    if entity_config[CONF_DOMAIN_DATA][CONF_MOTOR] in "OUTPUTS":
        entity = LcnOutputsCover(entity_config, host_name, device_connection)
    else:  # in RELAYS
        entity = LcnRelayCover(entity_config, host_name, device_connection)
    return entity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LCN cover entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_COVER:
            entities.append(create_lcn_cover_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnOutputsCover(LcnEntity, CoverEntity):
    """Representation of a LCN cover connected to output ports."""

    def __init__(self, config, host_id, address_connection):
        """Initialize the LCN cover."""
        super().__init__(config, host_id, address_connection)

        self.output_ids = [
            pypck.lcn_defs.OutputPort["OUTPUTUP"].value,
            pypck.lcn_defs.OutputPort["OUTPUTDOWN"].value,
        ]
        if CONF_REVERSE_TIME in config[CONF_DOMAIN_DATA]:
            self.reverse_time = pypck.lcn_defs.MotorReverseTime[
                config[CONF_DOMAIN_DATA][CONF_REVERSE_TIME]
            ]
        else:
            self.reverse_time = None

        self._is_closed = False
        self._is_closing = False
        self._is_opening = False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTUP"]
            )
            await self.address_connection.activate_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTDOWN"]
            )

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTUP"]
            )
            await self.address_connection.cancel_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTDOWN"]
            )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._is_closed

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return True

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._is_opening = False
        self._is_closing = True
        state = pypck.lcn_defs.MotorStateModifier.DOWN
        self.address_connection.control_motors_outputs(state, self.reverse_time)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._is_closed = False
        self._is_opening = True
        self._is_closing = False
        state = pypck.lcn_defs.MotorStateModifier.UP
        self.address_connection.control_motors_outputs(state, self.reverse_time)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._is_closing = False
        self._is_opening = False
        state = pypck.lcn_defs.MotorStateModifier.STOP
        self.address_connection.control_motors_outputs(state)
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set cover states when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() not in self.output_ids
        ):
            return

        if input_obj.get_percent() > 0:  # motor is on
            if input_obj.get_output_id() == self.output_ids[0]:
                self._is_opening = True
                self._is_closing = False
            else:  # self.output_ids[1]
                self._is_opening = False
                self._is_closing = True
            self._is_closed = self._is_closing
        else:  # motor is off
            # cover is assumed to be closed if we were in closing state before
            self._is_closed = self._is_closing
            self._is_closing = False
            self._is_opening = False

        self.async_write_ha_state()


class LcnRelayCover(LcnEntity, CoverEntity):
    """Representation of a LCN cover connected to relays."""

    def __init__(self, config, host_id, address_connection):
        """Initialize the LCN cover."""
        super().__init__(config, host_id, address_connection)

        self.motor = pypck.lcn_defs.MotorPort[config[CONF_DOMAIN_DATA][CONF_MOTOR]]
        self.motor_port_onoff = self.motor.value * 2
        self.motor_port_updown = self.motor_port_onoff + 1

        self._is_closed = False
        self._is_closing = False
        self._is_opening = False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.address_connection.is_group():
            await self.address_connection.activate_status_request_handler(self.motor)

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.address_connection.is_group():
            await self.address_connection.cancel_status_request_handler(self.motor)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._is_closed

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return True

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._is_opening = False
        self._is_closing = True
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.DOWN
        self.address_connection.control_motors_relays(states)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._is_closed = False
        self._is_opening = True
        self._is_closing = False
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.UP
        self.address_connection.control_motors_relays(states)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._is_closing = False
        self._is_opening = False
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.STOP
        self.address_connection.control_motors_relays(states)
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set cover states when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        states = input_obj.states  # list of boolean values (relay on/off)
        if states[self.motor_port_onoff]:  # motor is on
            self._is_opening = not states[self.motor_port_updown]  # set direction
            self._is_closing = states[self.motor_port_updown]  # set direction
        else:  # motor is off
            self._is_opening = False
            self._is_closing = False
            self._is_closed = states[self.motor_port_updown]

        self.async_write_ha_state()
