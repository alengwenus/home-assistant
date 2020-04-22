"""Web socket API for Local Control Network devices."""

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

TYPE = "type"
ID = "id"


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "lcn/modules"})
async def websocket_get_modules(hass, connection, msg):
    """Get LCN modules."""
    modules = [{"name": "Module_01"}, {"name": "Module_02"}]

    # zha_gateway = hass.data[DATA_LCN][DATA_ZHA_GATEWAY]
    # devices = [device.async_get_info() for device in zha_gateway.devices.values()]

    connection.send_result(msg[ID], modules)


@callback
def async_load_websocket_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_modules)
