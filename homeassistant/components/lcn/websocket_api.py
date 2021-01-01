"""Web socket API for Local Control Network devices."""

import asyncio
from operator import itemgetter
from typing import Tuple

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_RESOURCE,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_HARDWARE_SERIAL,
    CONF_HARDWARE_TYPE,
    CONF_SOFTWARE_SERIAL,
    CONNECTION,
    DOMAIN,
)
from .helpers import (  # async_register_lcn_address_devices,
    DeviceConnectionType,
    async_update_device_config,
    async_update_lcn_address_devices,
    generate_unique_id,
    get_device_config,
    get_device_connection,
    get_entity_config,
    get_resource,
)
from .schemas import (
    ADDRESS_SCHEMA,
    DOMAIN_DATA_BINARY_SENSOR,
    DOMAIN_DATA_CLIMATE,
    DOMAIN_DATA_COVER,
    DOMAIN_DATA_LIGHT,
    DOMAIN_DATA_SCENE,
    DOMAIN_DATA_SENSOR,
    DOMAIN_DATA_SWITCH,
)

TYPE = "type"
ID = "id"
ATTR_HOST_ID = "host_id"
ATTR_NAME = "name"
ATTR_RESOURCE = "resource"
ATTR_SEGMENT_ID = "segment_id"
ATTR_ADDRESS_ID = "address_id"
ATTR_IS_GROUP = "is_group"
ATTR_ENTITIES = "entities"
ATTR_DOMAIN = "domain"
ATTR_DOMAIN_DATA = "domain_data"


def sort_lcn_config_entry(config_entry: ConfigEntry):
    """Sort given config_entry."""

    # sort devices_config
    config_entry.data[CONF_DEVICES].sort(key=itemgetter(CONF_ADDRESS))

    # sort entities_config
    config_entry.data[CONF_ENTITIES].sort(key=itemgetter(ATTR_DOMAIN, ATTR_RESOURCE))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "lcn/hosts"})
async def websocket_get_hosts(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Get LCN hosts."""
    config_entries = hass.config_entries.async_entries(DOMAIN)

    hosts = [
        {
            CONF_NAME: config_entry.title,
            CONF_ID: config_entry.entry_id,
            CONF_IP_ADDRESS: config_entry.data[CONF_IP_ADDRESS],
            CONF_PORT: config_entry.data[CONF_PORT],
        }
        for config_entry in config_entries
    ]

    connection.send_result(msg[ID], hosts)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "lcn/devices", vol.Required(ATTR_HOST_ID): cv.string}
)
async def websocket_get_device_configs(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Get device configs."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    sort_lcn_config_entry(config_entry)
    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/device",
        vol.Required(ATTR_HOST_ID): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
async def websocket_get_device_config(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Get device config."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    device_config = get_device_config(msg[CONF_ADDRESS], config_entry)
    connection.send_result(msg[ID], device_config)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/entities",
        vol.Required(ATTR_HOST_ID): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
async def websocket_get_entity_configs(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Get entities configs."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    sort_lcn_config_entry(config_entry)
    entity_configs = [
        entity_config
        for entity_config in config_entry.data[CONF_ENTITIES]
        if entity_config[CONF_ADDRESS] == msg[CONF_ADDRESS]
    ]
    connection.send_result(msg[ID], entity_configs)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "lcn/device/scan", vol.Required(ATTR_HOST_ID): cv.string}
)
async def websocket_scan_devices(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Scan for new devices."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    host_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
    await host_connection.scan_modules()

    lock = asyncio.Lock()
    await asyncio.gather(
        *[
            async_create_or_update_device(device_connection, config_entry, lock)
            for device_connection in host_connection.address_conns.values()
            if not device_connection.is_group
        ]
    )

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # create/update devices in device regsitry
    await hass.async_create_task(async_update_lcn_address_devices(hass, config_entry))

    connection.send_result(msg[ID], config_entry.data[CONF_DEVICES])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/device/add",
        vol.Required(ATTR_HOST_ID): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(ATTR_NAME): cv.string,
    }
)
async def websocket_add_device(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Add a device."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    result = await hass.async_create_task(
        add_device(hass, config_entry, msg[CONF_ADDRESS])
    )

    if result:
        # sort config_entry
        sort_lcn_config_entry(config_entry)

        # schedule config_entry for save
        hass.config_entries.async_update_entry(config_entry)

        # create/update devices in device regsitry
        await hass.async_create_task(
            async_update_lcn_address_devices(hass, config_entry)
        )

    # return the device config, not all devices !!!
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/device/delete",
        vol.Required(ATTR_HOST_ID): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
    }
)
async def websocket_delete_device(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Delete a device."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    device_registry = await dr.async_get_registry(hass)
    delete_device(config_entry, device_registry, msg[CONF_ADDRESS])

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
        vol.Required(ATTR_HOST_ID): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_DOMAIN): cv.string,
        vol.Required(ATTR_DOMAIN_DATA): vol.Any(
            DOMAIN_DATA_BINARY_SENSOR,
            DOMAIN_DATA_CLIMATE,
            DOMAIN_DATA_COVER,
            DOMAIN_DATA_LIGHT,
            DOMAIN_DATA_SCENE,
            DOMAIN_DATA_SENSOR,
            DOMAIN_DATA_SWITCH,
        ),
    }
)
async def websocket_add_entity(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Add an entity."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return
    device_config = get_device_config(msg[CONF_ADDRESS], config_entry)
    if device_config is None:
        return

    unique_id = generate_unique_id(
        device_config[CONF_ADDRESS],
        (msg[ATTR_DOMAIN], msg[ATTR_DOMAIN_DATA]),
    )

    entity_registry = await er.async_get_registry(hass)
    entity_id = entity_registry.async_get_entity_id(
        msg[ATTR_DOMAIN], DOMAIN, f"{msg[ATTR_HOST_ID]}-{unique_id}"
    )

    if entity_id:
        result = False
    else:
        domain_name = msg[ATTR_DOMAIN]
        domain_data = msg[ATTR_DOMAIN_DATA]
        resource = get_resource(domain_name, domain_data).lower()
        entity_config = {
            CONF_ADDRESS: msg[CONF_ADDRESS],
            CONF_NAME: msg[ATTR_NAME],
            ATTR_RESOURCE: resource,
            ATTR_DOMAIN: domain_name,
            ATTR_DOMAIN_DATA: domain_data,
        }

        # Create new entity and add to corresponding component
        callbacks = hass.data[DOMAIN][msg[ATTR_HOST_ID]][ADD_ENTITIES_CALLBACKS]
        async_add_entities, create_lcn_entity = callbacks[msg[ATTR_DOMAIN]]

        entity = create_lcn_entity(hass, entity_config, config_entry)
        async_add_entities([entity])

        # Add entity config to config_entry
        config_entry.data[CONF_ENTITIES].append(entity_config)

        # sort config_entry
        sort_lcn_config_entry(config_entry)

        # schedule config_entry for save
        hass.config_entries.async_update_entry(config_entry)

        result = True

    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "lcn/entity/delete",
        vol.Required(ATTR_HOST_ID): cv.string,
        vol.Required(CONF_ADDRESS): ADDRESS_SCHEMA,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
    }
)
async def websocket_delete_entity(
    hass: HomeAssistantType, connection: ActiveConnection, msg: dict
) -> None:
    """Delete an entity."""
    config_entry = hass.config_entries.async_get_entry(msg[ATTR_HOST_ID])
    if config_entry is None:
        return

    device_registry = await dr.async_get_registry(hass)
    delete_entity(
        config_entry,
        device_registry,
        msg[CONF_ADDRESS],
        msg[CONF_DOMAIN],
        msg[CONF_RESOURCE],
    )

    # sort config_entry
    sort_lcn_config_entry(config_entry)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)

    # return the device config, not all devices !!!
    connection.send_result(msg[ID])


async def add_device(
    hass: HomeAssistantType, config_entry: ConfigEntry, address: Tuple[int, int, bool]
) -> bool:
    """Add a device to config_entry and device_registry."""
    if get_device_config(address, config_entry):
        return False  # device_config already in config_entry

    device_config = {
        CONF_ADDRESS: address,
        ATTR_NAME: "",
        CONF_HARDWARE_SERIAL: -1,
        CONF_SOFTWARE_SERIAL: -1,
        CONF_HARDWARE_TYPE: -1,
    }

    # add device_config to config_entry
    config_entry.data[CONF_DEVICES].append(device_config)

    # update device info from LCN
    device_connection = get_device_connection(hass, address, config_entry)
    await async_update_device_config(device_connection, device_config)

    return True


def delete_device(
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    address: Tuple[int, int, bool],
) -> None:
    """Delete a device from config_entry and device_registry."""
    device_config = get_device_config(address, config_entry)
    if device_config is None:
        return

    # delete all child devices (and entities)
    for entity_config in config_entry.data[CONF_ENTITIES][:]:
        if entity_config[CONF_ADDRESS] == address:
            delete_entity(
                config_entry,
                device_registry,
                entity_config[CONF_ADDRESS],
                entity_config[CONF_DOMAIN],
                entity_config[CONF_RESOURCE],
            )

    # now delete module/group device
    # identifiers = {(DOMAIN, unique_id)}
    identifiers = {(DOMAIN, config_entry.entry_id, *address)}
    device = device_registry.async_get_device(identifiers, set())

    if device:
        device_registry.async_remove_device(device.id)
        config_entry.data[CONF_DEVICES].remove(device_config)


def delete_entity(
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    address: Tuple[int, int, bool],
    domain: str,
    resource: str,
) -> None:
    """Delete an entity from config_entry and device_registry/entity_registry."""
    entity_config = get_entity_config(address, domain, resource, config_entry)

    identifiers = {(DOMAIN, config_entry.entry_id, *address, domain, resource)}
    entity_device = device_registry.async_get_device(identifiers, set())

    if entity_device:
        # removes entity from device_registry and from entity_registry
        device_registry.async_remove_device(entity_device.id)
        config_entry.data[CONF_ENTITIES].remove(entity_config)


async def async_create_or_update_device(
    device_connection: DeviceConnectionType,
    config_entry: ConfigEntry,
    lock: asyncio.Lock,
) -> None:
    """Create or update device in config_entry according to given device_connection."""
    address = (
        device_connection.seg_id,
        device_connection.addr_id,
        device_connection.is_group,
    )
    async with lock:  # prevent simultaneous access to config_entry
        for device_config in config_entry.data[CONF_DEVICES]:
            if device_config[CONF_ADDRESS] == address:
                if device_config[CONF_ADDRESS][2]:
                    device_config[CONF_NAME] = ""
                break  # device already in config_entry
        else:
            # create new device_entry
            device_config = {
                CONF_ADDRESS: address,
                CONF_NAME: "",
                CONF_HARDWARE_SERIAL: -1,
                CONF_SOFTWARE_SERIAL: -1,
                CONF_HARDWARE_TYPE: -1,
            }
            config_entry.data[CONF_DEVICES].append(device_config)

        # update device_entry
        await async_update_device_config(device_connection, device_config)


@callback
def async_load_websocket_api(hass: HomeAssistantType) -> None:
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
