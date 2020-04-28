"""Support for LCN devices."""
import logging

import pypck
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_HOST,
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
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity import Entity

from . import websocket_api as wsapi
from .const import (
    BINSENSOR_PORTS,
    CONF_ADDRESS_ID,
    CONF_CLIMATES,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_DIMMABLE,
    CONF_IS_GROUP,
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
    CONF_SEGMENT_ID,
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
    address_repr,
    convert_to_config_entry_data,
    has_unique_connection_names,
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
        vol.Optional(CONF_OUTPUTS): vol.All(
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
                    cv.ensure_list, has_unique_connection_names, [CONNECTION_SCHEMA]
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


async def async_create_devices(hass, config_entry, connection):
    """Create devices for PCHK connection and modules / groups."""
    device_registry = await dr.async_get_registry(hass)

    # create device for PCHK (hub)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data[CONF_NAME])},
        connections={(config_entry.data[CONF_HOST], config_entry.data[CONF_PORT])},
        manufacturer="Issendorff",
        name=config_entry.data[CONF_NAME],
        model="PCHK",
    )

    # get all LCN module/group addresses
    for platform in [
        CONF_SWITCHES,
        CONF_LIGHTS,
        CONF_BINARY_SENSORS,
        CONF_CLIMATES,
        CONF_COVERS,
        CONF_SCENES,
        CONF_SENSORS,
    ]:
        if platform in config_entry.data:
            addresses = {
                pypck.lcn_addr.LcnAddr(
                    entity_config[CONF_SEGMENT_ID],
                    entity_config[CONF_ADDRESS_ID],
                    entity_config[CONF_IS_GROUP],
                )
                for entity_config in config_entry.data[platform]
            }

    # initialize all modules/groups and get info
    for address in addresses:
        address_connection = connection.get_address_conn(address)
        if not address.is_group():
            await address_connection.serial_known
            address_name = await address_connection.request_name()
            # address_comment = await address_connection.request_comment()

            # create device for module
            device_registry.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                identifiers={
                    (
                        DOMAIN,
                        config_entry.data[CONF_NAME],
                        address_repr(address_connection),
                    )
                },
                manufacturer="Issendorff",
                name=f"{address_name} " f"({address_repr(address_connection).upper()})",
                model=address_connection.hw_type,
                sw_version=f"{address_connection.software_serial:06X}",
                via_device=(DOMAIN, config_entry.data[CONF_NAME]),
            )


async def async_setup_entry(hass, config_entry):
    """Set up a connection to PCHK host from a config entry."""
    name = config_entry.data[CONF_NAME]
    host = config_entry.data[CONF_HOST]
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
    if name not in hass.data[DATA_LCN][CONF_CONNECTIONS]:
        connection = pypck.connection.PchkConnectionManager(
            hass.loop,
            host,
            port,
            username,
            password,
            settings=settings,
            connection_id=name,
        )
        try:
            # establish connection to PCHK server
            await hass.async_create_task(connection.async_connect(timeout=15))
            hass.data[DATA_LCN][CONF_CONNECTIONS][name] = connection
            _LOGGER.info('LCN connected to "%s"', name)
        except pypck.connection.PchkAuthenticationError:
            _LOGGER.warning('Authentication on PCHK "%s" failed.', name)
            return False
        except pypck.connection.PchkLicenseError:
            _LOGGER.warning(
                'Maximum number of connections on PCHK "%s" was '
                "reached. An additional license key is required.",
                name,
            )
            return False
        except pypck.connection.PchkLcnNotConnectedError:
            _LOGGER.warning("No connection to the LCN hardware bus.")
            return False
        except TimeoutError:
            _LOGGER.warning('Connection to PCHK "%s" failed.', name)
            return False

        await async_create_devices(hass, config_entry, connection)

        # forward config_entry to platforms
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(config_entry, "switch")
        )

    # load the wepsocket api
    wsapi.async_load_websocket_api(hass)

    return True


async def async_unload_entry(hass, config_entry):
    """Close connection to PCHK host represented by config_entry."""
    name = config_entry.data[CONF_NAME]
    if name in hass.data[DATA_LCN][CONF_CONNECTIONS]:
        connection = hass.data[DATA_LCN][CONF_CONNECTIONS].pop(name)
        await connection.async_close()
    return True


async def async_setup(hass, config):
    """Set up the LCN component."""
    if DATA_LCN not in hass.data:
        hass.data[DATA_LCN] = {}
    if CONF_CONNECTIONS not in hass.data[DATA_LCN]:
        hass.data[DATA_LCN][CONF_CONNECTIONS] = {}

    if DOMAIN not in config:
        return True

    # initialize a config_flow for all LCN configurations read from
    # configuration.yaml
    config_entries_data = convert_to_config_entry_data(config[DOMAIN])

    for config_entry_data in config_entries_data:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config_entry_data,
            )
        )
    return True

    conf_connections = config[DOMAIN][CONF_CONNECTIONS]
    connections = []
    for conf_connection in conf_connections:
        connection_name = conf_connection.get(CONF_NAME)

        settings = {
            "SK_NUM_TRIES": conf_connection[CONF_SK_NUM_TRIES],
            "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[
                conf_connection[CONF_DIM_MODE]
            ],
        }

        connection = pypck.connection.PchkConnectionManager(
            hass.loop,
            conf_connection[CONF_HOST],
            conf_connection[CONF_PORT],
            conf_connection[CONF_USERNAME],
            conf_connection[CONF_PASSWORD],
            settings=settings,
            connection_id=connection_name,
        )

        try:
            # establish connection to PCHK server
            await hass.async_create_task(connection.async_connect(timeout=15))
            connections.append(connection)
            _LOGGER.info('LCN connected to "%s"', connection_name)
        except TimeoutError:
            _LOGGER.error('Connection to PCHK server "%s" failed', connection_name)
            return False

    hass.data[DATA_LCN][CONF_CONNECTIONS] = connections

    # load platforms
    for component, conf_key in (
        ("binary_sensor", CONF_BINARY_SENSORS),
        ("climate", CONF_CLIMATES),
        ("cover", CONF_COVERS),
        ("light", CONF_LIGHTS),
        ("scene", CONF_SCENES),
        ("sensor", CONF_SENSORS),
        ("switch", CONF_SWITCHES),
    ):
        if conf_key in config[DOMAIN]:
            hass.async_create_task(
                async_load_platform(
                    hass, component, DOMAIN, config[DOMAIN][conf_key], config
                )
            )

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

    return True


class LcnDevice(Entity):
    """Parent class for all devices associated with the LCN component."""

    def __init__(self, config, address_connection):
        """Initialize the LCN device."""
        self.config = config
        self.address_connection = address_connection
        self._name = config[CONF_NAME]

    @property
    def connection_id(self):
        """Return the connection identifier of related PCHK connection."""
        return self.address_connection.conn.connection_id

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.connection_id}/{address_repr(self.address_connection)}/"

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Issendorff",
            "model": self.address_connection.hw_type,
            "via_device": (DOMAIN, self.connection_id),
        }

    @property
    def should_poll(self):
        """Lcn device entity pushes its state to HA."""
        return False

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        self.address_connection.register_for_inputs(self.input_received)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def input_received(self, input_obj):
        """Set state/value when LCN input object (command) is received."""
        raise NotImplementedError("Pure virtual function.")
