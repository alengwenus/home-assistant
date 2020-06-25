"""Support for LCN scenes."""
from typing import Any

import pypck

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE, Scene
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES, CONF_HOST

from .const import (
    CONF_CONNECTIONS,
    CONF_DOMAIN_DATA,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_SCENE,
    CONF_TRANSITION,
    CONF_UNIQUE_DEVICE_ID,
    DATA_LCN,
    OUTPUT_PORTS,
)
from .helpers import get_device_address, get_device_config
from .lcn_entity import LcnEntity


def create_lcn_scene_entity(hass, entity_config, config_entry):
    """Set up an entity for this domain."""
    host_name = config_entry.data[CONF_HOST]
    host = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    device_config = get_device_config(
        entity_config[CONF_UNIQUE_DEVICE_ID], config_entry
    )
    addr = pypck.lcn_addr.LcnAddr(*get_device_address(device_config))
    device_connection = host.get_address_conn(addr)
    entity = LcnScene(entity_config, device_connection)

    return entity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LCN switch entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_SCENE:
            entities.append(create_lcn_scene_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnScene(LcnEntity, Scene):
    """Representation of a LCN scene."""

    def __init__(self, config, address_connection):
        """Initialize the LCN scene."""
        super().__init__(config, address_connection)

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
        self.address_connection.activate_scene(
            self.register_id,
            self.scene_id,
            self.output_ports,
            self.relay_ports,
            self.transition,
        )
