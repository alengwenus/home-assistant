"""Helpers for LCN component."""
import asyncio
import logging
import re

import pypck
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ADDRESS_ID,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_IS_GROUP,
    CONF_SEGMENT_ID,
    CONF_SK_NUM_TRIES,
    DATA_LCN,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Regex for address validation
PATTERN_ADDRESS = re.compile(
    "^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)\\.(?P<type>m|g)?(?P<id>\\d+)$"
)


PLATFORM_LOOKUP = {
    "binary_sensors": "binary_sensor",
    "climates": "climate",
    "covers": "cover",
    "lights": "light",
    "scenses": "scene",
    "sensors": "sensor",
    "switches": "switch",
}


def generate_unique_id(
    host_name,
    address=None,
    platform_config=None,  # (platform_name, platform_data)
    domain=DOMAIN,
):
    """Generate a unique_id from the given parameters."""
    unique_id = f"{domain}.{host_name}"
    if address:
        is_group = "g" if address[2] else "m"
        unique_id += f".{is_group}{address[0]:03d}{address[1]:03d}"
        if platform_config:
            platform_name, platform_data = platform_config
            if platform_name in ["switch", "light"]:
                resource = f'{platform_data["output"]}'.lower()
            elif platform_name in ["binary_sensor", "sensor"]:
                resource = f'{platform_data["source"]}'.lower()
            elif platform_name == "cover":
                resource = f'{platform_data["motor"]}'.lower()
            elif platform_name == "climate":
                resource = f'{platform_data["setpoint"]}.{platform_data["source"]}'
            elif platform_name == "scenes":
                resource = f'{platform_data["register"]}.{platform_data["scene"]}'
            else:
                raise ValueError("Unknown platform.")
            unique_id += f".{platform_name}.{resource}"
    return unique_id


def import_lcn_config(lcn_config):
    """Convert lcn settings from configuration.yaml to config_entries data."""
    data = {}
    for connection in lcn_config[CONF_CONNECTIONS]:
        host = {
            "unique_id": generate_unique_id(connection[CONF_NAME]),
            CONF_HOST: connection[CONF_NAME],
            CONF_IP_ADDRESS: connection[CONF_HOST],
            CONF_PORT: connection[CONF_PORT],
            CONF_USERNAME: connection[CONF_USERNAME],
            CONF_PASSWORD: connection[CONF_PASSWORD],
            CONF_SK_NUM_TRIES: connection[CONF_SK_NUM_TRIES],
            CONF_DIM_MODE: connection[CONF_DIM_MODE],
            CONF_DEVICES: [],
        }
        data[host[CONF_HOST]] = host

    for platform_name, platform_config in lcn_config.items():
        if platform_name == CONF_CONNECTIONS:
            continue
        # loop over entities in configuration.yaml
        for platform_data in platform_config:
            # remove name and address from platform_data
            entity_name = platform_data.pop(CONF_NAME)
            address, host_name = platform_data.pop(CONF_ADDRESS)

            if host_name is None:
                host_name = DEFAULT_NAME

            # check if we have a new device config
            unique_device_id = generate_unique_id(host_name, address)
            for device_config in data[host_name][CONF_DEVICES]:
                if unique_device_id == device_config["unique_id"]:
                    break
            else:  # create new device_config
                device_config = {
                    "unique_id": unique_device_id,
                    CONF_NAME: "",
                    CONF_SEGMENT_ID: address[0],
                    CONF_ADDRESS_ID: address[1],
                    CONF_IS_GROUP: address[2],
                    "hardware_serial": 0,
                    "software_serial": 0,
                    "hardware_type": 0,
                    CONF_ENTITIES: [],
                }

                data[host_name][CONF_DEVICES].append(device_config)

            # insert entity config
            unique_entity_id = generate_unique_id(
                host_name, address, (PLATFORM_LOOKUP[platform_name], platform_data)
            )
            for entity_config in device_config[CONF_ENTITIES]:
                if unique_entity_id == entity_config["unique_id"]:
                    _LOGGER.warning("Unique_id %s already defined.", unique_entity_id)
                    break
            else:  # create new entity_config
                entity_config = {
                    "unique_id": unique_entity_id,
                    CONF_NAME: entity_name,
                    "resource": unique_entity_id.split(".", 4)[4],
                    "platform": PLATFORM_LOOKUP[platform_name],
                    "platform_data": platform_data.copy(),
                }
                device_config[CONF_ENTITIES].append(entity_config)

    config_entries_data = data.values()
    return config_entries_data


async def async_update_lcn_device_info(hass, config_entry):
    """Request device names from LCN modules and updates config_entry."""
    host_name = config_entry.data[CONF_HOST]
    lcn_connection = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    for device_config in config_entry.data[CONF_DEVICES]:
        if device_config[CONF_IS_GROUP]:
            device_name = f"Group  {device_config[CONF_ADDRESS_ID]:d}"
            device_hardware_serial = 0
            device_software_serial = 0
            device_hardware_type = 0
        else:
            addr = pypck.lcn_addr.LcnAddr(
                device_config[CONF_SEGMENT_ID],
                device_config[CONF_ADDRESS_ID],
                device_config[CONF_IS_GROUP],
            )
            # get module info
            device_connection = lcn_connection.get_address_conn(addr)
            try:
                await asyncio.wait_for(device_connection.serial_known, timeout=3)
            except asyncio.TimeoutError:
                continue

            device_name = await device_connection.request_name()
            device_hardware_serial = device_connection.hardware_serial
            device_software_serial = device_connection.software_serial
            device_hardware_type = device_connection.hw_type

        device_config[CONF_NAME] = device_name
        device_config["hardware_serial"] = device_hardware_serial
        device_config["software_serial"] = device_software_serial
        device_config["hardware_type"] = device_hardware_type


def address_repr(address_connection):
    """Give a representation of the hardware address."""
    # host_name = address_connection.conn.connection_id
    address_type = "g" if address_connection.is_group() else "m"
    segment_id = address_connection.get_seg_id()
    address_id = address_connection.get_id()
    return f"{address_type}{segment_id:03d}{address_id:03d}"


async def get_address_connections_from_config_entry(hass, config_entry):
    """Get all address_connections for given config_entry."""
    address_connections = set()
    host_name = config_entry.data[CONF_HOST]
    lcn_connection = hass.data[DATA_LCN][CONF_CONNECTIONS][host_name]
    for device_config in config_entry.data[CONF_DEVICES]:
        addr = pypck.lcn_addr.LcnAddr(
            device_config[CONF_SEGMENT_ID],
            device_config[CONF_ADDRESS_ID],
            device_config[CONF_IS_GROUP],
        )
        address_connection = lcn_connection.get_address_conn(addr)
        address_connections.add(address_connection)
        if not address_connection.is_group():
            await address_connection.serial_known
    return address_connections


async def async_register_lcn_host_device(hass, config_entry):
    """Register LCN host for given config_entry."""
    device_registry = await dr.async_get_registry(hass)
    host_name = config_entry.data[CONF_HOST]
    unique_host_id = config_entry.data["unique_id"]
    identifiers = {(DOMAIN, unique_host_id)}
    device = device_registry.async_get_device(identifiers, set())
    if device:  # update device properties if already in registry
        return
    else:
        device = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=identifiers,
            manufacturer="LCN",
            name=f"{host_name}",
            model="PCHK",
        )


async def async_register_lcn_address_devices(hass, config_entry):
    """Register LCN modules and groups defined in config_entry as devices.

    The name of all given address_connections is collected and the devices
    are updated.
    """
    unique_host_id = config_entry.data["unique_id"]
    host_identifier = (DOMAIN, unique_host_id)
    device_registry = await dr.async_get_registry(hass)
    # host_device = device_registry.async_get_device({host_identifier}, set())
    # devices_temp = list(device_registry.devices)

    device_data = dict(
        config_entry_id=config_entry.entry_id,
        manufacturer="LCN",
        via_device=host_identifier,
    )

    for device_config in config_entry.data[CONF_DEVICES]:
        unique_device_id = device_config["unique_id"]
        device_name = device_config[CONF_NAME]
        identifiers = {(DOMAIN, unique_device_id)}

        if device_config[CONF_IS_GROUP]:
            # get group info
            device_model = f"group ({unique_device_id.split('.', 2)[2]})"
        else:
            # get module info
            device_model = f"module ({unique_device_id.split('.', 2)[2]})"
            device_data.update(sw_version=f"{device_config['software_serial']:06X}")

        device_data.update(
            name=device_name, identifiers=identifiers, model=device_model
        )
        device = device_registry.async_get_device(identifiers, set())
        if device:  # update device properties if already in registry
            device_registry.async_update_device(device.id, name=device_name)
        else:
            device = device_registry.async_get_or_create(**device_data)

    # for device in devices_temp:
    #     await device_registry.async_remove_device(device.id)


async def async_register_lcn_devices(hass, config_entry):
    """Register LCN host and all devices for given config_entry."""
    await async_register_lcn_host_device(hass, config_entry)
    await async_register_lcn_address_devices(hass, config_entry)


# def get_connection(hosts, host_name=None):
#     """Return the connection object from list."""
#     if host_name is None:
#         host = hosts[0]
#     else:
#         for host in hosts:
#             if host.host_name == host_name:
#                 break
#         else:
#             raise ValueError("Unknown host_name.")
#     return host


def has_unique_host_names(hosts):
    """Validate that all connection names are unique.

    Use 'pchk' as default connection_name (or add a numeric suffix if
    pchk' is already in use.
    """
    suffix = 0
    for host in hosts:
        host_name = host.get(CONF_NAME)
        if host_name is None:
            if suffix == 0:
                host[CONF_NAME] = DEFAULT_NAME
            else:
                host[CONF_NAME] = f"{DEFAULT_NAME}{suffix:d}"
            suffix += 1

    schema = vol.Schema(vol.Unique())
    schema([host.get(CONF_NAME) for host in hosts])
    return hosts


def is_address(value):
    """Validate the given address string.

    Examples for S000M005 at myhome:
        myhome.s000.m005
        myhome.s0.m5
        myhome.0.5    ("m" is implicit if missing)

    Examples for s000g011
        myhome.0.g11
        myhome.s0.g11
    """
    matcher = PATTERN_ADDRESS.match(value)
    if matcher:
        is_group = matcher.group("type") == "g"
        addr = (int(matcher.group("seg_id")), int(matcher.group("id")), is_group)
        conn_id = matcher.group("conn_id")
        return addr, conn_id
    raise vol.error.Invalid("Not a valid address string.")


def is_relays_states_string(states_string):
    """Validate the given states string and return states list."""
    if len(states_string) == 8:
        states = []
        for state_string in states_string:
            if state_string == "1":
                state = "ON"
            elif state_string == "0":
                state = "OFF"
            elif state_string == "T":
                state = "TOGGLE"
            elif state_string == "-":
                state = "NOCHANGE"
            else:
                raise vol.error.Invalid("Not a valid relay state string.")
            states.append(state)
        return states
    raise vol.error.Invalid("Wrong length of relay state string.")


def is_key_lock_states_string(states_string):
    """Validate the given states string and returns states list."""
    if len(states_string) == 8:
        states = []
        for state_string in states_string:
            if state_string == "1":
                state = "ON"
            elif state_string == "0":
                state = "OFF"
            elif state_string == "T":
                state = "TOGGLE"
            elif state_string == "-":
                state = "NOCHANGE"
            else:
                raise vol.error.Invalid("Not a valid key lock state string.")
            states.append(state)
        return states
    raise vol.error.Invalid("Wrong length of key lock state string.")
