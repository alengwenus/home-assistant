"""Helpers for LCN component."""
import asyncio
import logging
import re
from typing import List, Optional, Tuple, Type, Union

import pypck
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_ADDRESS_ID,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_DOMAIN_DATA,
    CONF_HARDWARE_SERIAL,
    CONF_HARDWARE_TYPE,
    CONF_IS_GROUP,
    CONF_SEGMENT_ID,
    CONF_SK_NUM_TRIES,
    CONF_SOFTWARE_SERIAL,
    CONF_UNIQUE_DEVICE_ID,
    CONNECTION,
    DEFAULT_NAME,
    DOMAIN,
)

# typing
DeviceConnectionType = Union[
    pypck.module.ModuleConnection, pypck.module.GroupConnection
]
PchkConnectionManagerType = Type[pypck.connection.PchkConnectionManager]
InputType = Type[pypck.inputs.Input]

_LOGGER = logging.getLogger(__name__)

# Regex for address validation
PATTERN_ADDRESS = re.compile(
    "^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)\\.(?P<type>m|g)?(?P<id>\\d+)$"
)


DOMAIN_LOOKUP = {
    "binary_sensors": "binary_sensor",
    "climates": "climate",
    "covers": "cover",
    "lights": "light",
    "scenes": "scene",
    "sensors": "sensor",
    "switches": "switch",
}


def get_resource(domain_name: str, domain_data: ConfigType) -> str:
    """Return the reosurce for the specified domain_data."""
    if domain_name in ["switch", "light"]:
        return f'{domain_data["output"]}'
    if domain_name in ["binary_sensor", "sensor"]:
        return f'{domain_data["source"]}'
    if domain_name == "cover":
        return f'{domain_data["motor"]}'
    if domain_name == "climate":
        return f'{domain_data["source"]}.{domain_data["setpoint"]}'
    if domain_name == "scene":
        return f'{domain_data["register"]}.{domain_data["scene"]}'
    raise ValueError("Unknown domain.")


def generate_unique_id(
    address: Optional[Tuple[int, int, bool]] = None,
    domain_config: Optional[Tuple[str, ConfigType]] = None,
):
    """Generate a unique_id from the given parameters."""
    unique_id = ""
    if address:
        is_group = "g" if address[2] else "m"
        unique_id += f"{is_group}{address[0]:03d}{address[1]:03d}"
        if domain_config:
            resource = get_resource(*domain_config)
            unique_id += f"-{resource}".lower()
    return unique_id


#
# Import from configuration.yaml to ConfigEntries
#


def import_lcn_config(lcn_config: ConfigType) -> List[ConfigType]:
    """Convert lcn settings from configuration.yaml to config_entries data."""
    data = {}
    for connection in lcn_config[CONF_CONNECTIONS]:
        host = {
            # CONF_UNIQUE_ID: generate_unique_id(connection[CONF_NAME]),
            CONF_HOST: connection[CONF_NAME],
            CONF_IP_ADDRESS: connection[CONF_HOST],
            CONF_PORT: connection[CONF_PORT],
            CONF_USERNAME: connection[CONF_USERNAME],
            CONF_PASSWORD: connection[CONF_PASSWORD],
            CONF_SK_NUM_TRIES: connection[CONF_SK_NUM_TRIES],
            CONF_DIM_MODE: connection[CONF_DIM_MODE],
            CONF_DEVICES: [],
            CONF_ENTITIES: [],
        }
        data[connection[CONF_NAME]] = host

    for domain, domain_config in lcn_config.items():
        if domain == CONF_CONNECTIONS:
            continue
        domain_name = DOMAIN_LOOKUP[domain]
        # loop over entities in configuration.yaml
        for domain_data in domain_config:
            # remove name and address from domain_data
            entity_name = domain_data.pop(CONF_NAME)
            address, host_name = domain_data.pop(CONF_ADDRESS)

            if host_name is None:
                host_name = DEFAULT_NAME

            # check if we have a new device config
            unique_device_id = generate_unique_id(address)
            for device_config in data[host_name][CONF_DEVICES]:
                if unique_device_id == device_config[CONF_UNIQUE_ID]:
                    break
            else:  # create new device_config
                device_config = {
                    CONF_UNIQUE_ID: unique_device_id,
                    CONF_NAME: "",
                    CONF_SEGMENT_ID: address[0],
                    CONF_ADDRESS_ID: address[1],
                    CONF_IS_GROUP: address[2],
                    CONF_HARDWARE_SERIAL: -1,
                    CONF_SOFTWARE_SERIAL: -1,
                    CONF_HARDWARE_TYPE: -1,
                }

                data[host_name][CONF_DEVICES].append(device_config)

            resource = get_resource(domain_name, domain_data).lower()
            for entity_config in data[host_name][CONF_ENTITIES]:
                if (
                    unique_device_id == entity_config[CONF_UNIQUE_DEVICE_ID]
                    and resource == entity_config[CONF_RESOURCE]
                    and domain_name == entity_config[CONF_DOMAIN]
                ):
                    break
            else:  # create new entity_config
                entity_config = {
                    CONF_UNIQUE_DEVICE_ID: unique_device_id,
                    CONF_NAME: entity_name,
                    CONF_RESOURCE: resource,
                    CONF_DOMAIN: domain_name,
                    CONF_DOMAIN_DATA: domain_data.copy(),
                }
                data[host_name][CONF_ENTITIES].append(entity_config)

    config_entries_data = list(data.values())
    return config_entries_data


#
# Register LCN devices from ConfigEntry (if not already registered)
#


async def async_update_lcn_host_device(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Register LCN host for given config_entry."""
    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer="Issendorff",
        name=config_entry.title,
        model="PCHK",
    )


async def async_update_lcn_address_devices(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Register LCN modules and groups defined in config_entry as devices.

    The name of all given device_connections is collected and the devices
    are updated.
    """
    host_identifier = (DOMAIN, config_entry.entry_id)
    device_registry = await dr.async_get_registry(hass)

    device_data = dict(manufacturer="Issendorff")

    for device_config in config_entry.data[CONF_DEVICES]:
        unique_device_id = device_config[CONF_UNIQUE_ID]
        device_name = device_config[CONF_NAME]
        # identifiers = {(DOMAIN, unique_device_id)}
        identifiers = {(DOMAIN, config_entry.entry_id, unique_device_id)}

        if device_config[CONF_IS_GROUP]:
            # get group info
            # device_model = f"group ({unique_device_id.split('.', 2)[2]})"
            device_model = f"group ({unique_device_id})"
        else:
            # get module info
            # device_model = f"module ({unique_device_id.split('.', 2)[2]})"
            device_model = f"module ({unique_device_id})"
            device_data.update(sw_version=f"{device_config[CONF_SOFTWARE_SERIAL]:06X}")

        device_data.update(name=device_name, model=device_model)
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=identifiers,
            via_device=host_identifier,
            **device_data,
        )


#
# Get device infos from LCN
#


async def async_update_device_config(
    device_connection: DeviceConnectionType, device_config: ConfigType
):
    """Fill missing values in device_config from LCN."""
    if not device_config[CONF_IS_GROUP]:
        await device_connection.serial_known
        if device_config[CONF_HARDWARE_SERIAL] == -1:
            device_config[CONF_HARDWARE_SERIAL] = device_connection.hardware_serial
        if device_config[CONF_SOFTWARE_SERIAL] == -1:
            device_config[CONF_SOFTWARE_SERIAL] = device_connection.software_serial
        if device_config[CONF_HARDWARE_TYPE] == -1:
            device_config[CONF_HARDWARE_TYPE] = device_connection.hardware_type.value

    if device_config[CONF_NAME] == "":
        if device_config[CONF_IS_GROUP] or device_connection.hardware_serial == -1:
            module_type = "Group" if device_config[CONF_IS_GROUP] else "Module"
            device_name = (
                f"{module_type} "
                f"{device_config[CONF_SEGMENT_ID]:03d}/"
                f"{device_config[CONF_ADDRESS_ID]:03d}"
            )
        else:
            device_name = await device_connection.request_name()
        device_config[CONF_NAME] = device_name


async def async_update_config_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Fill missing values in config_entry with information from LCN."""
    coros = []
    for device_config in config_entry.data[CONF_DEVICES]:
        device_connection = get_device_connection(
            hass, device_config[CONF_UNIQUE_ID], config_entry
        )
        coros.append(async_update_device_config(device_connection, device_config))

    await asyncio.gather(*coros)

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry)


def get_config_entry(hass: HomeAssistantType, host_id: str) -> Optional[ConfigEntry]:
    """Return the config_entry with given host."""
    return hass.config_entries.async_get_entry(host_id)


def get_device_config(
    unique_device_id: str, config_entry: ConfigEntry
) -> Optional[ConfigType]:
    """Return the configuration for given unique_device_id."""
    for device_config in config_entry.data[CONF_DEVICES]:
        if device_config[CONF_UNIQUE_ID] == unique_device_id:
            return device_config
    return None


def get_entity_config(
    unique_device_id: str, domain: str, resource: str, config_entry: ConfigEntry
) -> ConfigType:
    """Return the configuration for given unique_entity_id."""
    return next(
        entity_config
        for entity_config in config_entry.data[CONF_ENTITIES]
        if (
            entity_config[CONF_UNIQUE_DEVICE_ID] == unique_device_id
            and entity_config[CONF_DOMAIN] == domain
            and entity_config[CONF_RESOURCE] == resource
        )
    )


def get_device_address(device_config: ConfigType) -> Tuple[int, int, bool]:
    """Return a tuple with address information."""
    return (
        device_config[CONF_SEGMENT_ID],
        device_config[CONF_ADDRESS_ID],
        device_config[CONF_IS_GROUP],
    )


def get_device_connection(
    hass: HomeAssistantType, unique_device_id: str, config_entry: ConfigEntry
) -> Optional[DeviceConnectionType]:
    """Return a lcn device_connection."""
    device_config = get_device_config(unique_device_id, config_entry)
    if device_config:
        host_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
        addr = pypck.lcn_addr.LcnAddr(*get_device_address(device_config))
        device_connection = host_connection.get_address_conn(addr)
        return device_connection
    return None


def get_connection(
    hosts: List[PchkConnectionManagerType], host_name: Optional[str] = None
) -> PchkConnectionManagerType:
    """Return the connection object from list."""
    if host_name is None:
        host = hosts[0]
    else:
        for host in hosts:
            if host.host_name == host_name:
                break
        else:
            raise ValueError("Unknown host_name.")
    return host


def has_unique_host_names(hosts: List[ConfigType]) -> List[ConfigType]:
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


def is_address(value: str) -> Tuple[Tuple[int, int, bool], str]:
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


def is_relays_states_string(states_string: str) -> List[str]:
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


def is_key_lock_states_string(states_string: str) -> List[str]:
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
