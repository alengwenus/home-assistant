"""Test for the LCN climate platform."""

from pypck.inputs import ModStatusVar, Unknown
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import Var, VarUnit, VarValue

from homeassistant.components.climate import DOMAIN as DOMAIN_CLIMATE
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)

from .conftest import MockModuleConnection, setup_platform

from tests.async_mock import call, patch


@patch.object(MockModuleConnection, "activate_status_request_handler")
async def test_setup_lcn_climate(activate_status_request_handler, hass, entry):
    """Test the setup of climate."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    assert device_connection
    calls = [call(Var.VAR1), call(Var.R1VARSETPOINT)]
    activate_status_request_handler.assert_has_awaits(calls, any_order=True)
    assert activate_status_request_handler.await_count == 2


async def test_entity_state(hass, entry):
    """Test state of entity."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)

    state = hass.states.get("climate.climate1")
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_TARGET_TEMPERATURE
    assert set(state.attributes[ATTR_HVAC_MODES]) == {HVAC_MODE_HEAT, HVAC_MODE_OFF}
    assert state.attributes[ATTR_MIN_TEMP] == 0.0
    assert state.attributes[ATTR_MAX_TEMP] == 40.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_entity_attributes(hass, entry):
    """Test the attributes of an entity."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    await setup_platform(hass, entry, DOMAIN_CLIMATE)

    entity = entity_registry.async_get("climate.climate1")

    assert entity
    assert entity.unique_id == f"{entry.entry_id}-m000007-var1.r1varsetpoint"
    assert entity.original_name == "Climate1"


@patch.object(MockModuleConnection, "lock_regulator")
async def test_set_hvac_mode_heat(lock_regulator, hass, entry):
    """Test the hvac mode is set to heat."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)

    state = hass.states.get("climate.climate1")
    state.state = HVAC_MODE_OFF

    # command failed
    lock_regulator.return_value = False

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    lock_regulator.assert_awaited_with(0, False)

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state != HVAC_MODE_HEAT

    # command success
    lock_regulator.reset_mock(return_value=True)
    lock_regulator.return_value = True

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    lock_regulator.assert_awaited_with(0, False)

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVAC_MODE_HEAT


@patch.object(MockModuleConnection, "lock_regulator")
async def test_set_hvac_mode_off(lock_regulator, hass, entry):
    """Test the hvac mode is set off."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)

    state = hass.states.get("climate.climate1")
    state.state = HVAC_MODE_HEAT

    # command failed
    lock_regulator.return_value = False

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    await hass.async_block_till_done()
    lock_regulator.assert_awaited_with(0, True)

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state != HVAC_MODE_OFF

    # command success
    lock_regulator.reset_mock(return_value=True)
    lock_regulator.return_value = True

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    await hass.async_block_till_done()
    lock_regulator.assert_awaited_with(0, True)

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVAC_MODE_OFF


@patch.object(MockModuleConnection, "var_abs")
async def test_set_temperature(var_abs, hass, entry):
    """Test the temperature is set."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)

    state = hass.states.get("climate.climate1")
    state.state = HVAC_MODE_HEAT

    # wrong temperature set via service call with hig/low attributes
    var_abs.return_value = False

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.climate1",
            ATTR_TARGET_TEMP_LOW: 24.5,
            ATTR_TARGET_TEMP_HIGH: 25.5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    var_abs.assert_not_awaited()

    # command failed
    var_abs.reset_mock(return_value=True)
    var_abs.return_value = False

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.climate1", ATTR_TEMPERATURE: 25.5},
        blocking=True,
    )
    await hass.async_block_till_done()
    var_abs.assert_awaited_with(Var.R1VARSETPOINT, 25.5, VarUnit.CELSIUS)

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] != 25.5

    # command success
    var_abs.reset_mock(return_value=True)
    var_abs.return_value = True

    await hass.services.async_call(
        DOMAIN_CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.climate1", ATTR_TEMPERATURE: 25.5},
        blocking=True,
    )
    await hass.async_block_till_done()
    var_abs.assert_awaited_with(Var.R1VARSETPOINT, 25.5, VarUnit.CELSIUS)

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 25.5


async def test_pushed_current_temperature_status_change(hass, entry):
    """Test the climate changes its current temperature on status received."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue.from_celsius(25.5)

    input = ModStatusVar(address, Var.VAR1, temperature)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.5
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_pushed_setpoint_status_change(hass, entry):
    """Test the climate changes its setpoint on status received."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue.from_celsius(25.5)

    input = ModStatusVar(address, Var.R1VARSETPOINT, temperature)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] == 25.5


async def test_pushed_lock_status_change(hass, entry):
    """Test the climate changes its setpoint on status received."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue(0x8000)

    input = ModStatusVar(address, Var.R1VARSETPOINT, temperature)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVAC_MODE_OFF
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_pushed_wrong_input(hass, entry):
    """Test the climate handles wrong input correctly."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)
    device_connection = get_device_connection(hass, (0, 7, False), entry)

    await device_connection.async_process_input(Unknown("input"))
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_unload_config_entry(hass, entry):
    """Test the light is removed when the config entry is unloaded."""
    await setup_platform(hass, entry, DOMAIN_CLIMATE)
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_CLIMATE)
    assert not hass.states.get("climate.climate1")
