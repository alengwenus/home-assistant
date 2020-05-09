"""Web socket API for Local Control Network devices."""

import asyncio
from operator import itemgetter

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import callback

from .const import (
    CONF_ADDRESS_ID,
    CONF_CONNECTIONS,
    CONF_IS_GROUP,
    CONF_SEGMENT_ID,
    DATA_LCN,
    DOMAIN,
)
from .helpers import async_register_lcn_address_devices, generate_unique_id

# from homeassistant.helpers import entity_registry as er


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


def sort_lcn_config_entry(config_entry):
    """Sort given config_entry."""
    config_entry.data[CONF_DEVICES].sort(
        key=itemgetter(ATTR_IS_GROUP, ATTR_SEGMENT_ID, ATTR_ADDRESS_ID)
    )

    # sort entities_config
    for device_config in config_entry.data[CONF_DEVICES]:
        device_config[ATTR_ENTITIES].sort(key=itemgetter(ATTR_PLATFORM, ATTR_RESOURCE))


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

    sort_lcn_config_entry(config_entry)
    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "lcn/device/scan", vol.Required(ATTR_HOST): str}
)
async def websocket_scan_devices(hass, connection, msg):
    """Scan for new devices."""
    host_name = msg[ATTR_HOST]
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.data[CONF_HOST] == host_name:
            break

    host_connection = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    await host_connection.scan_modules()

    lock = asyncio.Lock()
    await asyncio.gather(
        *[
            async_create_or_update_device(device_connection, config_entry, lock)
            for device_connection in host_connection.address_conns.values()
            if not device_connection.is_group()
        ]
    )

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # create new devices
    await hass.async_create_task(async_register_lcn_address_devices(hass, config_entry))

    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/entity/delete",
        vol.Required(ATTR_HOST): str,
        vol.Required(ATTR_PLATFORM): str,
        vol.Required(ATTR_UNIQUE_ID): str,
    }
)
async def websocket_delete_entity(hass, connection, msg):
    """Get devices config."""
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.data[CONF_HOST] == msg[ATTR_HOST]:
            break

    print(msg)

    # entity_registry = await er.async_get_registry(hass)
    # entity = entity_registry.async_get_entity_id(DOMAIN, msg[ATTR_PLATFORM], msg[ATTR_UNIQUE_ID])
    # print(entity)

    # # sort config_entry
    # sort_lcn_config_entry(config_entry)

    # # schedule config_entry for save
    # hass.config_entries.async_update_entry(config_entry)

    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


async def async_create_or_update_device(device_connection, config_entry, lock):
    """Create or update device in config_entry according to given device_connection."""
    await device_connection.serial_known
    device_name = await device_connection.request_name()

    async with lock:  # prevent simultaneous access to config_entry
        for device in config_entry.data[CONF_DEVICES]:
            if (
                device[CONF_SEGMENT_ID] == device_connection.get_seg_id()
                and device[CONF_ADDRESS_ID] == device_connection.get_id()
                and device[CONF_IS_GROUP] == device_connection.is_group()
            ):
                break  # device already in config_entry
        else:
            # create new device_entry
            unique_device_id = generate_unique_id(
                config_entry.data[CONF_HOST],
                (
                    device_connection.get_seg_id(),
                    device_connection.get_id(),
                    device_connection.is_group(),
                ),
            )
            device = {
                "unique_id": unique_device_id,
                CONF_SEGMENT_ID: device_connection.get_seg_id(),
                CONF_ADDRESS_ID: device_connection.get_id(),
                CONF_IS_GROUP: device_connection.is_group(),
                CONF_ENTITIES: [],
            }
            config_entry.data[CONF_DEVICES].append(device)

        # update device_entry
        device.update(
            {
                CONF_NAME: device_name,
                "hardware_serial": device_connection.hardware_serial,
                "software_serial": device_connection.software_serial,
                "hardware_type": device_connection.hw_type,
            }
        )


@callback
def async_load_websocket_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_hosts)
    websocket_api.async_register_command(hass, websocket_get_config)
    websocket_api.async_register_command(hass, websocket_scan_devices)
    websocket_api.async_register_command(hass, websocket_delete_entity)
