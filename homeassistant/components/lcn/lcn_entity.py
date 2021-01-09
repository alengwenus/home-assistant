"""Entity class that represents LCN entity."""
from typing import Any, Dict

from homeassistant.const import CONF_ADDRESS, CONF_DOMAIN, CONF_NAME, CONF_RESOURCE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .helpers import DeviceConnectionType, InputType, generate_unique_id


class LcnEntity(Entity):
    """Parent class for all entities associated with the LCN component."""

    def __init__(
        self, config: ConfigType, host_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize the LCN device."""
        self.config = config
        self.host_id = host_id
        self.device_connection = device_connection
        self._unregister_for_inputs = None
        self._name = config[CONF_NAME]

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        unique_device_id = generate_unique_id(
            (
                self.device_connection.seg_id,
                self.device_connection.addr_id,
                self.device_connection.is_group,
            )
        )
        return f"{self.host_id}-{unique_device_id}-{self.config[CONF_RESOURCE]}"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device specific attributes."""
        if self.device_connection.is_group:
            hw_type = f"group ({self.unique_id.split('-', 2)[2]})"
        else:
            hw_type = f"module ({self.unique_id.split('-', 2)[2]})"

        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.host_id,
                    *self.config[CONF_ADDRESS],
                    self.config[CONF_DOMAIN],
                    self.config[CONF_RESOURCE],
                )
            },
            "name": self.name,
            "manufacturer": "Issendorff",
            "model": hw_type,
            "via_device": (DOMAIN, self.host_id, *self.config[CONF_ADDRESS]),
        }

    @property
    def should_poll(self) -> bool:
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        if not self.device_connection.is_group:
            self._unregister_for_inputs = self.device_connection.register_for_inputs(
                self.input_received
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unregister_for_inputs is not None:
            self._unregister_for_inputs()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj: InputType) -> None:
        """Set state/value when LCN input object (command) is received."""
