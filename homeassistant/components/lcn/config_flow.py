"""Config flow to configure the LCN integration."""
import logging
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize LCN flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_NAME, default='pchk')] = str
        data_schema[vol.Required(CONF_HOST, default='192.168.2.41')] = str
        data_schema[vol.Required(CONF_PORT, default=4114)] = vol.Coerce(int)
        data_schema[vol.Required(CONF_USERNAME, default='lcn')] = str
        data_schema[vol.Required(CONF_PASSWORD, default='lcn')] = str

        if user_input is None:
            return self.async_show_form(
                step_id='user',
                data_schema=vol.Schema(data_schema)
            )

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input
        )
