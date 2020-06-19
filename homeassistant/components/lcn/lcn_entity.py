"""Entity class that represents LCN entity."""
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .helpers import address_repr


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    def __init__(self, config, address_connection):
        """Initialize the LCN device."""
        self.config = config
        self.address_connection = address_connection
        self._name = config[CONF_NAME]
        self._unique_id = config["unique_id"]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device specific attributes."""
        if self.address_connection.is_group():
            hw_type = f"group ({self.unique_id.split('.', 2)[2]})"
        else:
            hw_type = f"module ({self.unique_id.split('.', 2)[2]})"
            # hw_type = f'0x{self.address_connection.hw_type:02X}'

        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "LCN",
            "model": hw_type,
            "via_device": (DOMAIN, address_repr(self.address_connection)),
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
        raise NotImplementedError("Pure virtual function.")
