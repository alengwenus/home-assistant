"""Support for LCN devices."""
import asyncio
import logging

import pypck

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import websocket_api as wsapi
from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DIM_MODE,
    CONF_SK_NUM_TRIES,
    CONNECTION,
    DOMAIN,
)
from .helpers import (
    async_update_config_entry,
    async_update_lcn_address_devices,
    async_update_lcn_host_device,
    import_lcn_config,
)
from .schemas import CONFIG_SCHEMA  # noqa: 401

# from .services import (
#     DynText,
#     Led,
#     LockKeys,
#     LockRegulator,
#     OutputAbs,
#     OutputRel,
#     OutputToggle,
#     Pck,
#     Relays,
#     SendKeys,
#     VarAbs,
#     VarRel,
#     VarReset,
# )

PLATFORMS = ["binary_sensor", "climate", "cover", "light", "scene", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up a connection to PCHK host from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    settings = {
        "SK_NUM_TRIES": config_entry.data[CONF_SK_NUM_TRIES],
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[config_entry.data[CONF_DIM_MODE]],
    }

    # connect to PCHK
    if config_entry.entry_id not in hass.data[DOMAIN]:
        lcn_connection = pypck.connection.PchkConnectionManager(
            config_entry.data[CONF_IP_ADDRESS],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            settings=settings,
            connection_id=config_entry.title,
        )
        try:
            # establish connection to PCHK server
            await hass.async_create_task(lcn_connection.async_connect(timeout=15))
        except pypck.connection.PchkAuthenticationError:
            _LOGGER.warning('Authentication on PCHK "%s" failed.', config_entry.title)
            return False
        except pypck.connection.PchkLicenseError:
            _LOGGER.warning(
                'Maximum number of connections on PCHK "%s" was '
                "reached. An additional license key is required.",
                config_entry.title,
            )
            return False
        except pypck.connection.PchkLcnNotConnectedError:
            _LOGGER.warning(
                'No connection to the LCN hardware bus of PCHK "%s".',
                config_entry.title,
            )
            return False
        except TimeoutError:
            _LOGGER.warning('Connection to PCHK "%s" failed.', config_entry.title)
            return False

        _LOGGER.info('LCN connected to "%s"', config_entry.title)
        hass.data[DOMAIN][config_entry.entry_id] = {
            CONNECTION: lcn_connection,
            ADD_ENTITIES_CALLBACKS: {},
        }
        config_entry.add_update_listener(async_entry_updated)

        # Update config_entry with LCN device serials
        await async_update_config_entry(hass, config_entry)

        # Cleanup device registry, if we imported from configuration.yaml to remove
        # orphans when entities were removed from configuration
        if config_entry.source == config_entries.SOURCE_IMPORT:
            device_registry = await dr.async_get_registry(hass)
            device_registry.async_clear_config_entry(config_entry.entry_id)
            config_entry.source = config_entries.SOURCE_USER

        await async_update_lcn_host_device(hass, config_entry)
        await async_update_lcn_address_devices(hass, config_entry)

        # forward config_entry to components
        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )

    # load the wepsocket api
    wsapi.async_load_websocket_api(hass)

    return True


async def async_unload_entry(hass, config_entry):
    """Close connection to PCHK host represented by config_entry."""
    # forward unloading to platforms
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        host = hass.data[DOMAIN].pop(config_entry.entry_id)
        await host[CONNECTION].async_close()

    return unload_ok


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the LCN component."""
    # register service calls
    # for service_name, service in (
    #     ("output_abs", OutputAbs),
    #     ("output_rel", OutputRel),
    #     ("output_toggle", OutputToggle),
    #     ("relays", Relays),
    #     ("var_abs", VarAbs),
    #     ("var_reset", VarReset),
    #     ("var_rel", VarRel),
    #     ("lock_regulator", LockRegulator),
    #     ("led", Led),
    #     ("send_keys", SendKeys),
    #     ("lock_keys", LockKeys),
    #     ("dyn_text", DynText),
    #     ("pck", Pck),
    # ):
    #     hass.services.async_register(
    #         DOMAIN, service_name, service(hass).async_call_service, service.schema
    #     )
    if DOMAIN not in config:
        return True

    # initialize a config_flow for all LCN configurations read from
    # configuration.yaml
    config_entries_data = import_lcn_config(config[DOMAIN])

    for config_entry_data in config_entries_data:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config_entry_data,
            )
        )
    return True


async def async_entry_updated(hass, config_entry):
    """Update listener to change connection name."""
    hass.data[DOMAIN][config_entry.entry_id][
        CONNECTION
    ].connection_id = config_entry.title
