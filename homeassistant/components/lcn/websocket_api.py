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
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ADDRESS_ID,
    CONF_CONNECTIONS,
    CONF_IS_GROUP,
    CONF_OUTPUT,
    CONF_SEGMENT_ID,
    DATA_LCN,
    DOMAIN,
    OUTPUT_PORTS,
    RELAY_PORTS,
)
from .helpers import (
    async_register_lcn_address_devices,
    generate_unique_id,
    get_config_entry,
    get_device_address,
    get_device_config,
    get_entity_config,
)
from .switch import create_lcn_switch_entity

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
ATTR_DOMAIN = "domain"
ATTR_DOMAIN_DATA = "domain_data"


def sort_lcn_config_entry(config_entry):
    """Sort given config_entry."""

    # sort devices_config
    config_entry.data[CONF_DEVICES].sort(
        key=itemgetter(ATTR_IS_GROUP, ATTR_SEGMENT_ID, ATTR_ADDRESS_ID)
    )

    # sort entities_config
    config_entry.data[CONF_ENTITIES].sort(key=itemgetter(ATTR_DOMAIN, ATTR_RESOURCE))


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
    {vol.Required(TYPE): "lcn/devices", vol.Required(ATTR_HOST): cv.string}
)
async def websocket_get_device_configs(hass, connection, msg):
    """Get device configs."""
    config_entry = get_config_entry(hass, msg[ATTR_HOST])
    sort_lcn_config_entry(config_entry)
    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/device",
        vol.Required(ATTR_HOST): cv.string,
        vol.Required("unique_device_id"): cv.string,
    }
)
async def websocket_get_device_config(hass, connection, msg):
    """Get device config."""
    config_entry = get_config_entry(hass, msg[ATTR_HOST])
    device_config = get_device_config(msg["unique_device_id"], config_entry)
    connection.send_result(msg[ID], device_config)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/entities",
        vol.Required(ATTR_HOST): cv.string,
        vol.Required("unique_device_id"): cv.string,
    }
)
async def websocket_get_entity_configs(hass, connection, msg):
    """Get entities configs."""
    config_entry = get_config_entry(hass, msg[ATTR_HOST])

    sort_lcn_config_entry(config_entry)
    entity_configs = [
        entity_config
        for entity_config in config_entry.data[CONF_ENTITIES]
        if entity_config["unique_device_id"] == msg["unique_device_id"]
    ]
    connection.send_result(msg[ID], entity_configs)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "lcn/device/scan", vol.Required(ATTR_HOST): cv.string}
)
async def websocket_scan_devices(hass, connection, msg):
    """Scan for new devices."""
    host_name = msg[ATTR_HOST]
    config_entry = get_config_entry(hass, host_name)

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
        vol.Required(TYPE): "lcn/device/add",
        vol.Required(ATTR_HOST): cv.string,
        vol.Required(ATTR_SEGMENT_ID): cv.positive_int,
        vol.Required(ATTR_ADDRESS_ID): cv.positive_int,
        vol.Required(ATTR_IS_GROUP): cv.boolean,
        vol.Required(ATTR_NAME): cv.string,
    }
)
async def websocket_add_device(hass, connection, msg):
    """Add a device."""
    config_entry = get_config_entry(hass, msg[ATTR_HOST])
    device_registry = await dr.async_get_registry(hass)

    address = (msg[ATTR_SEGMENT_ID], msg[ATTR_ADDRESS_ID], msg[ATTR_IS_GROUP])

    result = add_device(config_entry, device_registry, address, msg[ATTR_NAME])

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # return the device config, not all devices !!!
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/device/delete",
        vol.Required(ATTR_HOST): cv.string,
        vol.Required(ATTR_UNIQUE_ID): cv.string,
    }
)
async def websocket_delete_device(hass, connection, msg):
    """Delete a device."""
    config_entry = get_config_entry(hass, msg[ATTR_HOST])

    device_registry = await dr.async_get_registry(hass)
    delete_device(config_entry, device_registry, msg[ATTR_UNIQUE_ID])

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # return the device config, not all devices !!!
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/entity/add",
        vol.Required(ATTR_HOST): cv.string,
        vol.Required("unique_device_id"): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_DOMAIN): cv.string,
        vol.Required(ATTR_DOMAIN_DATA): {
            vol.Required(CONF_OUTPUT): vol.All(
                vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS)
            )
        },
    }
)
async def websocket_add_entity(hass, connection, msg):
    """Add an entity."""
    print(msg)
    config_entry = get_config_entry(hass, msg[ATTR_HOST])

    device_config = get_device_config(msg["unique_device_id"], config_entry)
    unique_id = generate_unique_id(
        msg[ATTR_HOST],
        get_device_address(device_config),
        (msg[ATTR_DOMAIN], msg[ATTR_DOMAIN_DATA]),
    )

    entity_config = {
        ATTR_UNIQUE_ID: unique_id,
        "unique_device_id": msg["unique_device_id"],
        CONF_NAME: msg[ATTR_NAME],
        ATTR_RESOURCE: unique_id.split(".", 4)[4],
        ATTR_DOMAIN: msg[ATTR_DOMAIN],
        ATTR_DOMAIN_DATA: msg[ATTR_DOMAIN_DATA],
    }

    # Create new entity and add to corresponding component
    entity = create_lcn_switch_entity(hass, entity_config, config_entry)

    component = hass.data[msg[ATTR_DOMAIN]]
    platform = component._platforms[config_entry.entry_id]

    hass.async_add_job(platform.async_add_entities([entity]))

    # Add entity config to config_entry
    config_entry.data[CONF_ENTITIES].append(entity_config)

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # return the device config, not all devices !!!
    result = True
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/entity/delete",
        vol.Required(ATTR_HOST): cv.string,
        vol.Required(ATTR_UNIQUE_ID): cv.string,
    }
)
async def websocket_delete_entity(hass, connection, msg):
    """Delete an entity."""
    config_entry = get_config_entry(hass, msg[ATTR_HOST])

    device_registry = await dr.async_get_registry(hass)
    delete_entity(config_entry, device_registry, msg[ATTR_UNIQUE_ID])

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # return the device config, not all devices !!!
    connection.send_result(msg[ID])


def add_device(config_entry, device_registry, address, name=""):
    """Add a device to config_entry and device_registry."""
    unique_host_id = config_entry.data["unique_id"]
    host_name = config_entry.data[ATTR_HOST]
    unique_device_id = generate_unique_id(host_name, address)

    # add device to device_registry
    identifiers = {(DOMAIN, unique_device_id)}
    if address[2]:  # is_group
        # get group info
        device_model = f"group ({unique_device_id.split('.', 2)[2]})"
    else:
        # get module info
        device_model = f"module ({unique_device_id.split('.', 2)[2]})"

    device_data = dict(
        config_entry_id=config_entry.entry_id,
        identifiers=identifiers,
        name=name,
        manufacturer="LCN",
        model=device_model,
        via_device=(DOMAIN, unique_host_id),
    )

    # check if device is in device_registry
    device = device_registry.async_get_device(identifiers, set())
    if device:
        return False
    device_registry.async_get_or_create(**device_data)

    # add device to config_entry
    device_config = {
        ATTR_UNIQUE_ID: unique_device_id,
        ATTR_NAME: name,
        ATTR_SEGMENT_ID: address[0],
        ATTR_ADDRESS_ID: address[1],
        ATTR_IS_GROUP: address[2],
        "hardware_serial": 0,
        "software_serial": 0,
        "hardware_type": 0,
    }

    config_entry.data[CONF_DEVICES].append(device_config)
    return True


def delete_device(config_entry, device_registry, unique_id):
    """Delete a device from config_entry and device_registry."""
    device_config = get_device_config(unique_id, config_entry)
    # delete all child devices (and entities)
    for entity_config in config_entry.data[CONF_ENTITIES][:]:
        if entity_config["unique_device_id"] == device_config[ATTR_UNIQUE_ID]:
            delete_entity(config_entry, device_registry, entity_config[ATTR_UNIQUE_ID])

    # now delete module/group device
    identifiers = {(DOMAIN, unique_id)}
    device = device_registry.async_get_device(identifiers, set())

    if device:
        device_registry.async_remove_device(device.id)
        config_entry.data[CONF_DEVICES].remove(device_config)


def delete_entity(config_entry, device_registry, unique_id):
    """Delete an entity from config_entry and device_registry/entity_registry."""
    entity_config = get_entity_config(unique_id, config_entry)

    identifiers = {(DOMAIN, unique_id)}
    entity_device = device_registry.async_get_device(identifiers, set())

    if entity_device:
        # removes entity from device_registry and from entity_registry
        device_registry.async_remove_device(entity_device.id)
        config_entry.data[CONF_ENTITIES].remove(entity_config)


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
    websocket_api.async_register_command(hass, websocket_get_device_config)
    websocket_api.async_register_command(hass, websocket_get_device_configs)
    websocket_api.async_register_command(hass, websocket_get_entity_configs)
    websocket_api.async_register_command(hass, websocket_scan_devices)
    websocket_api.async_register_command(hass, websocket_add_device)
    websocket_api.async_register_command(hass, websocket_delete_device)
    websocket_api.async_register_command(hass, websocket_add_entity)
    websocket_api.async_register_command(hass, websocket_delete_entity)
