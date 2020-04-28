"""Config flow to configure the LCN integration."""
from collections import OrderedDict
import logging

import pypck
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

from .const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DIM_MODES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate_connection(hass, user_input):
    name = user_input[CONF_NAME]
    host = user_input[CONF_HOST]
    port = user_input[CONF_PORT]
    username = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]
    sk_num_tries = user_input[CONF_SK_NUM_TRIES]
    dim_mode = user_input[CONF_DIM_MODE]

    settings = {
        "SK_NUM_TRIES": sk_num_tries,
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[dim_mode],
    }

    connection = pypck.connection.PchkConnectionManager(
        hass.loop,
        host,
        port,
        username,
        password,
        settings=settings,
        connection_id=name,
    )

    await connection.async_connect(timeout=5)
    _LOGGER.debug('Validated: LCN connected to "%s"', name)

    await connection.async_close()
    return True


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_NAME, default="pchk")] = str
        data_schema[vol.Required(CONF_HOST, default="192.168.2.41")] = str
        data_schema[vol.Required(CONF_PORT, default=4114)] = cv.positive_int
        data_schema[vol.Required(CONF_USERNAME, default="lcn")] = str
        data_schema[vol.Required(CONF_PASSWORD, default="lcn")] = str
        data_schema[vol.Required(CONF_SK_NUM_TRIES, default=0)] = cv.positive_int
        data_schema[vol.Required(CONF_DIM_MODE, default="STEPS200")] = vol.In(DIM_MODES)

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )

        try:
            # set a unique_id for this config flow
            # (alternatively return already existing entry)
            entry = await self.async_set_unique_id(user_input[CONF_NAME])
            if entry:
                return self.async_abort(reason="already_configured")
            await _validate_connection(self.hass, user_input)
        except pypck.connection.PchkAuthenticationError:
            return self.async_abort(reason="authentication_error")
        except pypck.connection.PchkLicenseError:
            return self.async_abort(reason="license_error")
        except pypck.connection.PchkLcnNotConnectedError:
            return self.async_abort(reason="lcn_not_connected_error")
        except TimeoutError:
            _LOGGER.error(
                'Connection to PCHK server "%s" failed.', user_input[CONF_NAME]
            )
            return self.async_abort(reason="connection_timeout")

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async def async_step_import(self, info):
        """Import existing configuration from LCN."""
        entry = await self.async_set_unique_id(info[CONF_NAME])
        if entry:
            await self.hass.config_entries.async_remove(entry.entry_id)

        return self.async_create_entry(
            title="{} (import from configuration.yaml)".format(info[CONF_NAME]),
            data=info,
        )
