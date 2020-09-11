"""Config flow to configure the LCN integration."""
from collections import OrderedDict
import logging
from typing import Optional, cast

import pypck
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DIM_MODES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate_connection(hass: HomeAssistantType, user_input: ConfigType) -> bool:
    host = user_input[CONF_IP_ADDRESS]
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
        hass.loop, host, port, username, password, settings=settings
    )

    await connection.async_connect(timeout=5)
    _LOGGER.debug("Validated: LCN connected.")

    await connection.async_close()
    return True


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> ConfigType:
        """Handle a flow initiated by the user."""
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_HOST, default="pchk")] = str
        data_schema[vol.Required(CONF_IP_ADDRESS, default="192.168.2.41")] = str
        data_schema[vol.Required(CONF_PORT, default=4114)] = cv.positive_int
        data_schema[vol.Required(CONF_USERNAME, default="lcn")] = str
        data_schema[vol.Required(CONF_PASSWORD, default="lcn")] = str
        data_schema[vol.Required(CONF_SK_NUM_TRIES, default=0)] = cv.positive_int
        data_schema[vol.Required(CONF_DIM_MODE, default="STEPS200")] = vol.In(DIM_MODES)

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )

        host_name = user_input.pop(CONF_HOST)

        try:
            hass = cast(HomeAssistantType, self.hass)
            await _validate_connection(hass, user_input)
        except pypck.connection.PchkAuthenticationError:
            return self.async_abort(reason="authentication_error")
        except pypck.connection.PchkLicenseError:
            return self.async_abort(reason="license_error")
        except pypck.connection.PchkLcnNotConnectedError:
            return self.async_abort(reason="lcn_not_connected_error")
        except TimeoutError:
            _LOGGER.error('Connection to PCHK server "%s" failed.', host_name)
            return self.async_abort(reason="connection_timeout")

        user_input[CONF_DEVICES] = []
        user_input[CONF_ENTITIES] = []

        return self.async_create_entry(title=host_name, data=user_input)

    async def async_step_import(self, info: ConfigType) -> ConfigType:
        """Import existing configuration from LCN."""
        # check if we already have a host with the same name configured
        host_name = info.pop(CONF_HOST)
        entry = await self.async_set_unique_id(host_name)
        if entry:
            # await self.hass.config_entries.async_remove(entry.entry_id)
            entry.source = config_entries.SOURCE_IMPORT
            hass = cast(HomeAssistantType, self.hass)
            hass.config_entries.async_update_entry(entry, data=info)
            return self.async_abort(reason="existing_configuration_updated")

        return self.async_create_entry(title=f"{host_name}", data=info,)
