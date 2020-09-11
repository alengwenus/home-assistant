"""Support for LCN scenes."""
from typing import Any, Callable, List

import pypck

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_DOMAIN_DATA,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_SCENE,
    CONF_TRANSITION,
    CONF_UNIQUE_DEVICE_ID,
    OUTPUT_PORTS,
)
from .helpers import DeviceConnectionType, get_device_connection
from .lcn_entity import LcnEntity


def create_lcn_scene_entity(
    hass: HomeAssistantType, entity_config: ConfigType, config_entry: ConfigEntry
) -> LcnEntity:
    """Set up an entity for this domain."""
    host_name = config_entry.entry_id
    device_connection = get_device_connection(
        hass, entity_config[CONF_UNIQUE_DEVICE_ID], config_entry
    )

    entity = LcnScene(entity_config, host_name, device_connection)
    return entity


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[LcnEntity]], None],
) -> None:
    """Set up LCN switch entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_SCENE:
            entities.append(create_lcn_scene_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnScene(LcnEntity, Scene):
    """Representation of a LCN scene."""

    def __init__(
        self, config: ConfigType, host_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize the LCN scene."""
        super().__init__(config, host_id, device_connection)

        self.register_id = config[CONF_DOMAIN_DATA][CONF_REGISTER]
        self.scene_id = config[CONF_DOMAIN_DATA][CONF_SCENE]
        self.output_ports = []
        self.relay_ports = []

        for port in config[CONF_DOMAIN_DATA][CONF_OUTPUTS]:
            if port in OUTPUT_PORTS:
                self.output_ports.append(pypck.lcn_defs.OutputPort[port])
            else:  # in RELEAY_PORTS
                self.relay_ports.append(pypck.lcn_defs.RelayPort[port])

        if config[CONF_DOMAIN_DATA][CONF_TRANSITION] is None:
            self.transition = None
        else:
            self.transition = pypck.lcn_defs.time_to_ramp_value(
                config[CONF_DOMAIN_DATA][CONF_TRANSITION]
            )

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        self.device_connection.activate_scene(
            self.register_id,
            self.scene_id,
            self.output_ports,
            self.relay_ports,
            self.transition,
        )
