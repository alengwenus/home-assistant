"""Support for LCN devices."""
import logging

import pypck
import voluptuous as vol

# from homeassistant.helpers.discovery import async_load_platform
from homeassistant import config_entries
from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

from . import websocket_api as wsapi
from .const import (
    BINSENSOR_PORTS,
    CONF_CLIMATES,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_DIMMABLE,
    CONF_LOCKABLE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_MOTOR,
    CONF_OUTPUT,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_REVERSE_TIME,
    CONF_SCENE,
    CONF_SCENES,
    CONF_SETPOINT,
    CONF_SK_NUM_TRIES,
    CONF_SOURCE,
    CONF_TRANSITION,
    DATA_LCN,
    DIM_MODES,
    DOMAIN,
    KEYS,
    LED_PORTS,
    LOGICOP_PORTS,
    MOTOR_PORTS,
    MOTOR_REVERSE_TIME,
    OUTPUT_PORTS,
    RELAY_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VAR_UNITS,
    VARIABLES,
)
from .helpers import (
    async_update_lcn_address_devices,
    async_update_lcn_device_names,
    async_update_lcn_device_serials,
    async_update_lcn_host_device,
    has_unique_host_names,
    import_lcn_config,
    is_address,
)
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

BINARY_SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_SOURCE): vol.All(
            vol.Upper, vol.In(SETPOINTS + KEYS + BINSENSOR_PORTS)
        ),
    }
)

CLIMATES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_SOURCE): vol.All(vol.Upper, vol.In(VARIABLES)),
        vol.Required(CONF_SETPOINT): vol.All(vol.Upper, vol.In(VARIABLES + SETPOINTS)),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_LOCKABLE, default=False): vol.Coerce(bool),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=TEMP_CELSIUS): vol.In(
            TEMP_CELSIUS, TEMP_FAHRENHEIT
        ),
    }
)

COVERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_MOTOR): vol.All(vol.Upper, vol.In(MOTOR_PORTS)),
        vol.Optional(CONF_REVERSE_TIME): vol.All(vol.Upper, vol.In(MOTOR_REVERSE_TIME)),
    }
)

LIGHTS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_OUTPUT): vol.All(
            vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS)
        ),
        vol.Optional(CONF_DIMMABLE, default=False): vol.Coerce(bool),
        vol.Optional(CONF_TRANSITION, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=486.0), lambda value: value * 1000
        ),
    }
)

SCENES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_REGISTER): vol.All(vol.Coerce(int), vol.Range(0, 9)),
        vol.Required(CONF_SCENE): vol.All(vol.Coerce(int), vol.Range(0, 9)),
        vol.Optional(CONF_OUTPUTS, default=[]): vol.All(
            cv.ensure_list, [vol.All(vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS))]
        ),
        vol.Optional(CONF_TRANSITION, default=None): vol.Any(
            vol.All(
                vol.Coerce(int),
                vol.Range(min=0.0, max=486.0),
                lambda value: value * 1000,
            ),
            None,
        ),
    }
)

SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_SOURCE): vol.All(
            vol.Upper,
            vol.In(
                VARIABLES
                + SETPOINTS
                + THRESHOLDS
                + S0_INPUTS
                + LED_PORTS
                + LOGICOP_PORTS
            ),
        ),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="native"): vol.All(
            vol.Upper, vol.In(VAR_UNITS)
        ),
    }
)

SWITCHES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): is_address,
        vol.Required(CONF_OUTPUT): vol.All(
            vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS)
        ),
    }
)

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SK_NUM_TRIES, default=0): cv.positive_int,
        vol.Optional(CONF_DIM_MODE, default="steps50"): vol.All(
            vol.Upper, vol.In(DIM_MODES)
        ),
        vol.Optional(CONF_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONNECTIONS): vol.All(
                    cv.ensure_list, has_unique_host_names, [CONNECTION_SCHEMA]
                ),
                vol.Optional(CONF_BINARY_SENSORS): vol.All(
                    cv.ensure_list, [BINARY_SENSORS_SCHEMA]
                ),
                vol.Optional(CONF_CLIMATES): vol.All(cv.ensure_list, [CLIMATES_SCHEMA]),
                vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
                vol.Optional(CONF_LIGHTS): vol.All(cv.ensure_list, [LIGHTS_SCHEMA]),
                vol.Optional(CONF_SCENES): vol.All(cv.ensure_list, [SCENES_SCHEMA]),
                vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSORS_SCHEMA]),
                vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCHES_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass, config_entry):
    """Set up a connection to PCHK host from a config entry."""
    host = config_entry.data[CONF_HOST]
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
    if host not in hass.data[DATA_LCN][CONF_CONNECTIONS]:
        lcn_connection = pypck.connection.PchkConnectionManager(
            hass.loop,
            host_address,
            port,
            username,
            password,
            settings=settings,
            connection_id=host,
        )
        try:
            # establish connection to PCHK server
            await hass.async_create_task(lcn_connection.async_connect(timeout=15))
            hass.data[DATA_LCN][CONF_CONNECTIONS][host] = lcn_connection
            _LOGGER.info('LCN connected to "%s"', host)
        except pypck.connection.PchkAuthenticationError:
            _LOGGER.warning('Authentication on PCHK "%s" failed.', host)
            return False
        except pypck.connection.PchkLicenseError:
            _LOGGER.warning(
                'Maximum number of connections on PCHK "%s" was '
                "reached. An additional license key is required.",
                host,
            )
            return False
        except pypck.connection.PchkLcnNotConnectedError:
            _LOGGER.warning("No connection to the LCN hardware bus.")
            return False
        except TimeoutError:
            _LOGGER.warning('Connection to PCHK "%s" failed.', host)
            return False

        # register LCN host, modules and groups in device registry
        # await hass.async_create_task(async_register_lcn_devices(hass, config_entry))

        # Update DeviceRegistry whenever ConfigEntry gets updated
        # to keep both in sync.
        # config_entry.add_update_listener(async_update_device_registry)

        await hass.async_create_task(async_update_lcn_host_device(hass, config_entry))
        await hass.async_create_task(
            async_update_lcn_address_devices(hass, config_entry)
        )

        # update config_entry with LCN device serials
        await hass.async_create_task(
            async_update_lcn_device_serials(hass, config_entry)
        )

        if config_entry.source == config_entries.SOURCE_IMPORT:
            await hass.async_create_task(
                async_update_lcn_device_names(hass, config_entry)
            )
            config_entry.source = config_entries.SOURCE_USER

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
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(config_entry, domain)
            )

    # load the wepsocket api
    wsapi.async_load_websocket_api(hass)

    return True


async def async_unload_entry(hass, config_entry):
    """Close connection to PCHK host represented by config_entry."""
    # forward unloading to platforms
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")

    host = config_entry.data[CONF_HOST]
    if host in hass.data[DATA_LCN][CONF_CONNECTIONS]:
        connection = hass.data[DATA_LCN][CONF_CONNECTIONS].pop(host)
        await connection.async_close()

    return True


async def async_setup(hass, config):
    """Set up the LCN component."""
    if DATA_LCN not in hass.data:
        hass.data[DATA_LCN] = {}
    if CONF_CONNECTIONS not in hass.data[DATA_LCN]:
        hass.data[DATA_LCN][CONF_CONNECTIONS] = {}

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
