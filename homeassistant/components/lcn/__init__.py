"""Support for LCN devices."""
import logging

import pypck

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, CONNECTION, DOMAIN
from .helpers import (
    async_update_config_entry,
    async_update_lcn_address_devices,
    async_update_lcn_host_device,
    import_lcn_config,
)
from .schemes import CONFIG_SCHEMA  # noqa: 401
from .services import (
    DynText,
    Led,
    LockKeys,
    LockRegulator,
    OutputAbs,
    OutputRel,
    OutputToggle,
    Pck,
    Relays,
    SendKeys,
    VarAbs,
    VarRel,
    VarReset,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up a connection to PCHK host from a config entry."""
    host_id = config_entry.entry_id
    host_address = config_entry.data[CONF_IP_ADDRESS]
    port = config_entry.data[CONF_PORT]
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    sk_num_tries = config_entry.data[CONF_SK_NUM_TRIES]
    dim_mode = config_entry.data[CONF_DIM_MODE]

    settings = {
        "SK_NUM_TRIES": sk_num_tries,
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[dim_mode],
    }

    # connect to PCHK
    if host_id not in hass.data[DOMAIN]:
        lcn_connection = pypck.connection.PchkConnectionManager(
            hass.loop,
            host_address,
            port,
            username,
            password,
            settings=settings,
            connection_id=host_id,
        )
        try:
            # establish connection to PCHK server
            await hass.async_create_task(lcn_connection.async_connect(timeout=15))
            _LOGGER.info('LCN connected to "%s"', config_entry.title)
            hass.data[DOMAIN][host_id] = {CONNECTION: lcn_connection}
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

        # Update config_entry with LCN device serials
        await hass.async_create_task(async_update_config_entry(hass, config_entry))

        # Cleanup device registry, if we imported from configuration.yaml to remove
        # orphans when entities were removed from configuration
        if config_entry.source == config_entries.SOURCE_IMPORT:
            device_registry = await dr.async_get_registry(hass)
            device_registry.async_clear_config_entry(config_entry.entry_id)
            config_entry.source = config_entries.SOURCE_USER

        await hass.async_create_task(async_update_lcn_host_device(hass, config_entry))

        await hass.async_create_task(
            async_update_lcn_address_devices(hass, config_entry)
        )

        # forward config_entry to components
        for domain in [
            "binary_sensor",
            "climate",
            "cover",
            "light",
            "scene",
            "sensor",
            "switch",
        ]:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, domain)
            )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: config_entries.ConfigEntry
) -> bool:
    """Close connection to PCHK host represented by config_entry."""
    # forward unloading to platforms
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")

    host_id = config_entry.entry_id
    if host_id in hass.data[DOMAIN]:
        host = hass.data[DOMAIN].pop(host_id)
        await host[CONNECTION].async_close()

    return True


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the LCN component."""
    hass.data[DOMAIN] = {}

    # register service calls
    for service_name, service in (
        ("output_abs", OutputAbs),
        ("output_rel", OutputRel),
        ("output_toggle", OutputToggle),
        ("relays", Relays),
        ("var_abs", VarAbs),
        ("var_reset", VarReset),
        ("var_rel", VarRel),
        ("lock_regulator", LockRegulator),
        ("led", Led),
        ("send_keys", SendKeys),
        ("lock_keys", LockKeys),
        ("dyn_text", DynText),
        ("pck", Pck),
    ):
        hass.services.async_register(
            DOMAIN, service_name, service(hass), service.schema
        )

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
