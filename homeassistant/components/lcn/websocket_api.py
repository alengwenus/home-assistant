"""Web socket API for Local Control Network devices."""

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import callback

from .const import CONF_PLATFORMS, DOMAIN

# from .helpers import address_repr


TYPE = "type"
ID = "id"
ATTR_HOST = "host"


def convert_config_entry(config_entry):
    """Convert the config entry to a format which can be transferred via websocket."""
    for platform_name, platform in config_entry.data[CONF_PLATFORMS].items():
        pass
    # config = {}


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
    """Get LCN modules."""
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.data[CONF_HOST] == msg[ATTR_HOST]:
            break

    # config = convert_config_entry(config_entry)

    config_temp = []
    connection.send_result(msg[ID], config_temp)


@callback
def async_load_websocket_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_hosts)
    websocket_api.async_register_command(hass, websocket_get_config)
