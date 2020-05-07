"""Web socket API for Local Control Network devices."""

from operator import itemgetter

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_CONNECTIONS, DATA_LCN, DOMAIN
from .helpers import generate_unique_id

TYPE = "type"
ID = "id"
ATTR_HOST = "host"
ATTR_NAME = "name"
ATTR_UNIQUE_ID = "unique_id"
ATTR_RESOURCE = "resource"
ATTR_SEGMENT_ID = "segment_id"
ATTR_ADDRESS_ID = "address_id"
ATTR_IS_GROUP = "is_group"
ATTR_ENTITIES = "entities"
ATTR_PLATFORM = "platform"
ATTR_PLATFORM_DATA = "platform_data"


async def convert_config_entry(hass, config_entry):
    """Convert the config entry to a format which can be transferred via websocket."""
    config = {}
    device_registry = await dr.async_get_registry(hass)

    for entity_config in config_entry.data[CONF_ENTITIES]:
        platform_name = entity_config["platform"]

        address = tuple(entity_config[CONF_ADDRESS])
        entity_name = entity_config[ATTR_NAME]
        unique_entity_id = entity_config["unique_id"]
        entity_resource = unique_entity_id.split(".", 4)[4]

        if address not in config:
            config[address] = {}

            unique_device_id = generate_unique_id(config_entry.data[CONF_HOST], address)
            identifiers = {(DOMAIN, unique_device_id)}
            lcn_device = device_registry.async_get_device(identifiers, set())
            config[address].update(
                {
                    ATTR_NAME: lcn_device.name,
                    ATTR_UNIQUE_ID: unique_device_id,
                    ATTR_SEGMENT_ID: address[0],
                    ATTR_ADDRESS_ID: address[1],
                    ATTR_IS_GROUP: address[2],
                    ATTR_ENTITIES: [],
                }
            )

        config[address][ATTR_ENTITIES].append(
            {
                ATTR_NAME: entity_name,
                ATTR_UNIQUE_ID: unique_entity_id,
                ATTR_PLATFORM: platform_name,
                ATTR_RESOURCE: entity_resource,
                ATTR_PLATFORM_DATA: entity_config["platform_data"],
            }
        )

    # cast devices_config to dict and sort
    devices_config = sorted(
        config.values(), key=itemgetter(ATTR_IS_GROUP, ATTR_SEGMENT_ID, ATTR_ADDRESS_ID)
    )

    # sort entities_config
    for device_config in devices_config:
        device_config[ATTR_ENTITIES].sort(key=itemgetter(ATTR_PLATFORM, ATTR_RESOURCE))

    return devices_config


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "lcn/hosts"})
async def websocket_get_hosts(hass, connection, msg):
    """Get LCN hosts."""
    config_entries = hass.config_entries.async_entries(DOMAIN)

    hosts = [
        {
            CONF_NAME: config_entry.data[CONF_HOST],
            CONF_IP_ADDRESS: config_entry.data[CONF_IP_ADDRESS],
            CONF_PORT: config_entry.data[CONF_PORT],
        }
        for config_entry in config_entries
    ]

    connection.send_result(msg[ID], hosts)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "lcn/config", vol.Required(ATTR_HOST): str}
)
async def websocket_get_config(hass, connection, msg):
    """Get devices config."""
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.data[CONF_HOST] == msg[ATTR_HOST]:
            break

    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "lcn/devices/scan", vol.Required(ATTR_HOST): str}
)
async def websocket_scan_devices(hass, connection, msg):
    """Scan for new devices."""
    host_name = msg[ATTR_HOST]
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.data[CONF_HOST] == host_name:
            break

    # create a set of all device addresses from config_entry
    entity_addresses = {
        tuple(entity[CONF_ADDRESS]) for entity in config_entry.data[ATTR_ENTITIES]
    }

    host_connection = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    await host_connection.scan_modules()

    for device_connection in host_connection.address_conns:
        address = (
            device_connection.get_seg_id(),
            device_connection.get_id(),
            device_connection.is_group(),
        )

        if address not in entity_addresses:
            pass
            # Problem!

        # print(config_entry.data)

    config = await convert_config_entry(hass, config_entry)
    print(config)

    connection.send_result(msg[ID], config)


@callback
def async_load_websocket_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_hosts)
    websocket_api.async_register_command(hass, websocket_get_config)
    websocket_api.async_register_command(hass, websocket_scan_devices)
