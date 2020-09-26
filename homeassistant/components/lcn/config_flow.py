"""Config flow to configure the LCN integration."""
import logging
from typing import Optional, cast

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> ConfigType:
        """Handle a flow initiated by the user."""
        return self.async_abort(reason="not_implemented")

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

        return self.async_create_entry(
            title=f"{host_name}",
            data=info,
        )
