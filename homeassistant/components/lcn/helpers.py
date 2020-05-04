"""Helpers for LCN component."""
import re

import pypck
import voluptuous as vol

from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.helpers import device_registry as dr

from .const import CONF_CONNECTIONS, CONF_PLATFORMS, DATA_LCN, DEFAULT_NAME, DOMAIN

# Regex for address validation
PATTERN_ADDRESS = re.compile(
    "^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)\\.(?P<type>m|g)?(?P<id>\\d+)$"
)


platform_lookup = {
    "binary_sensors": "binary_sensor",
    "climates": "climate",
    "covers": "cover",
    "lights": "light",
    "scenses": "scene",
    "sensors": "sensor",
    "switches": "switch",
}


def import_lcn_config(lcn_config):
    """Convert lcn settings from configuration.yaml to config_entries data."""
    data = {}
    for connection in lcn_config[CONF_CONNECTIONS]:
        host = connection.copy()
        host.update(
            {CONF_HOST: connection[CONF_NAME], CONF_IP_ADDRESS: connection[CONF_HOST]}
        )
        data[host[CONF_HOST]] = host
        data[host[CONF_HOST]][CONF_PLATFORMS] = {}

    for platform_name, platform_config in lcn_config.items():
        if platform_name == CONF_CONNECTIONS:
            continue
        for entity_config in platform_config:
            address, host_name = entity_config[CONF_ADDRESS]
            entity_config[CONF_ADDRESS] = address

            if host_name is None:
                host_name = DEFAULT_NAME

            if platform_lookup[platform_name] in data[host_name][CONF_PLATFORMS]:
                data[host_name][CONF_PLATFORMS][platform_lookup[platform_name]].append(
                    entity_config
                )
            else:
                data[host_name][CONF_PLATFORMS][platform_lookup[platform_name]] = [
                    entity_config
                ]

    config_entries_data = data.values()
    return config_entries_data


async def get_address_connections_from_config_entry(hass, config_entry):
    """Get all address_connections for given config_entry."""
    address_connections = set()
    lcn_connection = hass.data[DATA_LCN][CONF_CONNECTIONS][config_entry.data[CONF_HOST]]
    for entity_configs in config_entry.data[CONF_PLATFORMS].values():
        for entity_config in entity_configs:
            addr = pypck.lcn_addr.LcnAddr(*entity_config[CONF_ADDRESS])
            address_connection = lcn_connection.get_address_conn(addr)
            address_connections.add(address_connection)
            if not address_connection.is_group():
                await address_connection.serial_known
    return address_connections


def address_repr(address_connection):
    """Give a representation of the hardware address."""
    # host_name = address_connection.conn.connection_id
    address_type = "g" if address_connection.is_group() else "m"
    segment_id = address_connection.get_seg_id()
    address_id = address_connection.get_id()
    return f"{address_type}{segment_id:03d}{address_id:03d}"


async def async_register_lcn_host_device(hass, config_entry):
    """Register LCN host for given config_entry."""
    device_registry = await dr.async_get_registry(hass)
    host_name = config_entry.data[CONF_HOST]
    identifiers = {(DOMAIN, host_name)}
    device = device_registry.async_get_device(identifiers, set())
    if device:  # update device properties if already in registry
        return
    else:
        device = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=identifiers,
            manufacturer="Issendorff",
            name=f"{host_name}",
            model="PCHK",
        )


async def async_register_lcn_address_devices(hass, config_entry, address_connections):
    """Register LCN modules and groups defined in config_entry as devices.

    The name of all given address_connections is collected and the devices
    are updated.
    """
    host_name = config_entry.data[CONF_HOST]
    host_identifier = (DOMAIN, host_name)
    device_registry = await dr.async_get_registry(hass)
    # host_device = device_registry.async_get_device({host_identifier}, set())
    # devices_temp = list(device_registry.devices)

    device_data = dict(
        config_entry_id=config_entry.entry_id,
        manufacturer="Issendorff",
        via_device=host_identifier,
    )

    for address_connection in address_connections:
        identifiers = {(DOMAIN, address_repr(address_connection))}
        address_name = f"Group  {address_connection.get_id():d}"
        if address_connection.is_group():
            # get group info
            device_data.update(
                name=(
                    f"{address_name}" f" ({address_repr(address_connection).lower()})"
                ),
                model="group",
            )
        else:
            # get module info
            await address_connection.serial_known
            address_name = await address_connection.request_name()
            identifiers.add((DOMAIN, address_connection.hardware_serial,))
            device_data.update(
                name=(
                    f"{address_name}" f" ({address_repr(address_connection).lower()})"
                ),
                model="module",  # f'0x{address_connection.hw_type:02X}',
                sw_version=f"{address_connection.software_serial:06X}",
            )

        device_data.update(identifiers=identifiers)
        device = device_registry.async_get_device(identifiers, set())
        if device:  # update device properties if already in registry
            device_registry.async_update_device(device.id, name=address_name)
        else:
            device = device_registry.async_get_or_create(**device_data)

    # for device in devices_temp:
    #     await device_registry.async_remove_device(device.id)


async def async_register_lcn_devices(hass, config_entry):
    """Register LCN host and all devices for given config_entry."""
    address_connections = await get_address_connections_from_config_entry(
        hass, config_entry
    )
    await async_register_lcn_host_device(hass, config_entry)
    await async_register_lcn_address_devices(hass, config_entry, address_connections)


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
