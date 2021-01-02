"""Test for the LCN sensor platform."""
from unittest.mock import call, patch

from pypck.inputs import ModStatusLedsAndLogicOps, ModStatusVar
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import LedPort, LedStatus, LogicOpPort, LogicOpStatus, Var, VarValue

from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS

from .conftest import MockModuleConnection, setup_platform


@patch.object(MockModuleConnection, "activate_status_request_handler")
async def test_setup_lcn_sensor(activate_status_request_handler, hass, entry):
    """Test the setup of sensor."""
    await setup_platform(hass, entry, DOMAIN_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    assert device_connection
    calls = [
        call(Var.VAR1),
        call(Var.R1VARSETPOINT),
        call(LedPort.LED6),
        call(LogicOpPort.LOGICOP1),
    ]
    activate_status_request_handler.assert_has_awaits(calls, any_order=True)
    assert activate_status_request_handler.await_count == 4


async def test_entity_state(hass, entry):
    """Test state of entity."""
    await setup_platform(hass, entry, DOMAIN_SENSOR)

    state = hass.states.get("sensor.sensor_var1")
    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS

    state = hass.states.get("sensor.sensor_setpoint1")
    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS

    state = hass.states.get("sensor.sensor_led6")
    assert state

    state = hass.states.get("sensor.sensor_logicop1")
    assert state


async def test_entity_attributes(hass, entry):
    """Test the attributes of an entity."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    await setup_platform(hass, entry, DOMAIN_SENSOR)

    entity_var1 = entity_registry.async_get("sensor.sensor_var1")
    assert entity_var1
    assert entity_var1.unique_id == f"{entry.entry_id}-m000007-var1"
    assert entity_var1.original_name == "Sensor_Var1"

    entity_r1varsetpoint = entity_registry.async_get("sensor.sensor_setpoint1")
    assert entity_r1varsetpoint
    assert entity_r1varsetpoint.unique_id == f"{entry.entry_id}-m000007-r1varsetpoint"
    assert entity_r1varsetpoint.original_name == "Sensor_Setpoint1"

    entity_led6 = entity_registry.async_get("sensor.sensor_led6")
    assert entity_led6
    assert entity_led6.unique_id == f"{entry.entry_id}-m000007-led6"
    assert entity_led6.original_name == "Sensor_Led6"

    entity_logicop1 = entity_registry.async_get("sensor.sensor_logicop1")
    assert entity_logicop1
    assert entity_logicop1.unique_id == f"{entry.entry_id}-m000007-logicop1"
    assert entity_logicop1.original_name == "Sensor_LogicOp1"


async def test_pushed_variable_status_change(hass, entry):
    """Test the variable sensor changes its state on status received."""
    await setup_platform(hass, entry, DOMAIN_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    # push status variable
    input = ModStatusVar(address, Var.VAR1, VarValue.from_celsius(42))
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sensor_var1")
    assert state is not None
    assert float(state.state) == 42.0

    # push status setpoint
    input = ModStatusVar(address, Var.R1VARSETPOINT, VarValue.from_celsius(42))
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sensor_setpoint1")
    assert state is not None
    assert float(state.state) == 42.0


async def test_pushed_ledlogicop_status_change(hass, entry):
    """Test the led and logicop sensor changes its state on status received."""
    await setup_platform(hass, entry, DOMAIN_SENSOR)
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    states_led = [LedStatus.OFF] * 12
    states_logicop = [LogicOpStatus.NONE] * 4

    states_led[5] = LedStatus.ON
    states_logicop[0] = LogicOpStatus.ALL

    # push status led and logicop
    input = ModStatusLedsAndLogicOps(address, states_led, states_logicop)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sensor_led6")
    assert state is not None
    assert state.state == "on"

    state = hass.states.get("sensor.sensor_logicop1")
    assert state is not None
    assert state.state == "all"


async def test_unload_config_entry(hass, entry):
    """Test the sensor is removed when the config entry is unloaded."""
    await setup_platform(hass, entry, DOMAIN_SENSOR)
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_SENSOR)
    assert not hass.states.get("sensor.sensor_var1")
    assert not hass.states.get("sensor.sensor_setpoint1")
    assert not hass.states.get("sensor.sensor_led6")
    assert not hass.states.get("sensor.sensor_logicop1")
