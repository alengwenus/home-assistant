"""Test for the LCN binary sensor platform."""
from unittest.mock import call, patch

from pypck.inputs import ModStatusBinSensors, ModStatusKeyLocks, ModStatusVar
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import BinSensorPort, Key, Var, VarValue

from homeassistant.components.binary_sensor import DOMAIN as DOMAIN_BINARY_SENSOR
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import STATE_OFF, STATE_ON

from .conftest import MockModuleConnection, setup_platform


@patch.object(MockModuleConnection, "activate_status_request_handler")
async def test_setup_lcn_sensor(activate_status_request_handler, hass, entry):
    """Test the setup of binary sensor."""
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    assert device_connection
    calls = [call(Var.R1VARSETPOINT), call(BinSensorPort.BINSENSOR1), call(Key.A5)]
    activate_status_request_handler.assert_has_awaits(calls, any_order=True)
    assert activate_status_request_handler.await_count == 3


async def test_entity_state(hass, entry):
    """Test state of entity."""
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)

    state = hass.states.get("binary_sensor.sensor_lockregulator1")
    assert state

    state = hass.states.get("binary_sensor.binary_sensor1")
    assert state

    state = hass.states.get("binary_sensor.sensor_keylock")
    assert state


async def test_entity_attributes(hass, entry):
    """Test the attributes of an entity."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)

    entity_setpoint1 = entity_registry.async_get("binary_sensor.sensor_lockregulator1")
    assert entity_setpoint1
    assert entity_setpoint1.unique_id == f"{entry.entry_id}-m000007-r1varsetpoint"
    assert entity_setpoint1.original_name == "Sensor_LockRegulator1"

    entity_binsensor1 = entity_registry.async_get("binary_sensor.binary_sensor1")
    assert entity_binsensor1
    assert entity_binsensor1.unique_id == f"{entry.entry_id}-m000007-binsensor1"
    assert entity_binsensor1.original_name == "Binary_Sensor1"

    entity_keylock = entity_registry.async_get("binary_sensor.sensor_keylock")
    assert entity_keylock
    assert entity_keylock.unique_id == f"{entry.entry_id}-m000007-a5"
    assert entity_keylock.original_name == "Sensor_KeyLock"


async def test_pushed_lock_setpoint_status_change(hass, entry):
    """Test the lock setpoint sensor changes its state on status received."""
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    # push status lock setpoint
    input = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x8000))
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.sensor_lockregulator1")
    assert state is not None
    assert state.state == STATE_ON

    # push status unlock setpoint
    input = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x7FFF))
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.sensor_lockregulator1")
    assert state is not None
    assert state.state == STATE_OFF


async def test_pushed_binsensor_status_change(hass, entry):
    """Test the binary port sensor changes its state on status received."""
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    # push status binary port "off"
    input = ModStatusBinSensors(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.binary_sensor1")
    assert state is not None
    assert state.state == STATE_OFF

    # push status binary port "on"
    states[0] = True
    input = ModStatusBinSensors(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.binary_sensor1")
    assert state is not None
    assert state.state == STATE_ON


async def test_pushed_keylock_status_change(hass, entry):
    """Test the keylock sensor changes its state on status received."""
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [[False] * 8 for i in range(4)]

    # push status keylock "off"
    input = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.sensor_keylock")
    assert state is not None
    assert state.state == STATE_OFF

    # push status keylock "on"
    states[0][4] = True
    input = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.sensor_keylock")
    assert state is not None
    assert state.state == STATE_ON


async def test_unload_config_entry(hass, entry):
    """Test the binary sensor is removed when the config entry is unloaded."""
    await setup_platform(hass, entry, DOMAIN_BINARY_SENSOR)
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_BINARY_SENSOR)
    assert not hass.states.get("binary_sensor.sensor_lockregulator1")
    assert not hass.states.get("binary_sensor.binary_sensor1")
    assert not hass.states.get("bynary_sensor.sensor_keylock")
