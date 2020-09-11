"""Entity class that represents LCN entity."""

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import CONF_UNIQUE_ID
from .helpers import DeviceConnectionType, InputType


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    def __init__(
        self, config: ConfigType, host_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize the LCN device."""
        self.config = config
        self.host_id = host_id
        self.device_connection = device_connection
        self._name = config[CONF_NAME]

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.host_id}-{self.config[CONF_UNIQUE_ID]}"

    @property
    def should_poll(self) -> bool:
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.unregister_for_inputs = self.device_connection.register_for_inputs(
            self.input_received
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self.unregister_for_inputs()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj: InputType) -> None:
        """Set state/value when LCN input object (command) is received."""
