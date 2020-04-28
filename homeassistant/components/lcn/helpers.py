"""Helpers for LCN component."""
import re

import voluptuous as vol

from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import (
    CONF_ADDRESS_ID,
    CONF_CONNECTIONS,
    CONF_IS_GROUP,
    CONF_SEGMENT_ID,
    DEFAULT_NAME,
)

# Regex for address validation
PATTERN_ADDRESS = re.compile(
    "^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)\\.(?P<type>m|g)?(?P<id>\\d+)$"
)


def convert_to_config_entry_data(lcn_config):
    """Convert the config dictionary to config_entry data."""
    config = lcn_config.copy()
    data = {}
    connections = config.pop(CONF_CONNECTIONS)
    for connection in connections:
        connection_id = connection[CONF_NAME]
        data[connection_id] = connection

    for platform_name, platform_config in config.items():
        for entity_config in platform_config:
            # entity_address_config = entity_config.pop(CONF_ADDRESS)
            address, connection_id = entity_config.pop(CONF_ADDRESS)

            # address, connection_id = is_address(entity_address_config)
            segment_id = address[0]
            address_id = address[1]
            address_is_group = address[2]

            entity_config.update(
                {
                    CONF_ADDRESS_ID: address_id,
                    CONF_SEGMENT_ID: segment_id,
                    CONF_IS_GROUP: address_is_group,
                }
            )

            if connection_id is None:
                connection_id = DEFAULT_NAME

            if platform_name in data[connection_id]:
                data[connection_id][platform_name].append(entity_config)
            else:
                data[connection_id][platform_name] = [entity_config]

    config_entries_data = [config_entry_data for config_entry_data in data.values()]
    return config_entries_data


def get_connection(connections, connection_id=None):
    """Return the connection object from list."""
    if connection_id is None:
        connection = connections[0]
    else:
        for connection in connections:
            if connection.connection_id == connection_id:
                break
        else:
            raise ValueError("Unknown connection_id.")
    return connection


def has_unique_connection_names(connections):
    """Validate that all connection names are unique.

    Use 'pchk' as default connection_name (or add a numeric suffix if
    pchk' is already in use.
    """
    suffix = 0
    for connection in connections:
        connection_name = connection.get(CONF_NAME)
        if connection_name is None:
            if suffix == 0:
                connection[CONF_NAME] = DEFAULT_NAME
            else:
                connection[CONF_NAME] = f"{DEFAULT_NAME}{suffix:d}"
            suffix += 1

    schema = vol.Schema(vol.Unique())
    schema([connection.get(CONF_NAME) for connection in connections])
    return connections


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
