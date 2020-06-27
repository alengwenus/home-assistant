"""Entity class that represents LCN entity."""
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import CONF_UNIQUE_DEVICE_ID, CONF_UNIQUE_ID, DOMAIN

# from .helpers import address_repr


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    def __init__(self, config, host_id, address_connection):
        """Initialize the LCN device."""
        self.config = config
        self.host_id = host_id
        self.address_connection = address_connection
        self._name = config[CONF_NAME]
        # self._unique_id = config["unique_id"]

    @property
    def unique_id(self):
        """Return a unique ID."""
        # return f"{self.host_id}-{self.config[CONF_UNIQUE_ID]}"
        return f"{self.host_id}-{self.config[CONF_UNIQUE_ID]}"

    @property
    def device_info(self):
        """Return device specific attributes."""
        if self.address_connection.is_group():
            hw_type = f"group ({self.unique_id.split('-', 2)[2]})"
        else:
            hw_type = f"module ({self.unique_id.split('-', 2)[2]})"
            # hw_type = f'0x{self.address_connection.hw_type:02X}'

        return {
            "identifiers": {(DOMAIN, self.host_id, self.config[CONF_UNIQUE_ID])},
            "name": self.name,
            "manufacturer": "LCN",
            "model": hw_type,
            "via_device": (DOMAIN, self.host_id, self.config[CONF_UNIQUE_DEVICE_ID]),
            # "via_device": (DOMAIN, self.host_id, address_repr(self.address_connection)),
        }

    @property
    def should_poll(self):
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        self.unregister_for_inputs = self.address_connection.register_for_inputs(
            self.input_received
        )

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        self.unregister_for_inputs()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj):
        """Set state/value when LCN input object (command) is received."""
