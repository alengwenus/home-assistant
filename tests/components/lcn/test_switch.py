"""Test for the LCN switch platform."""
from pypck.lcn_defs import OutputPort, RelayPort, RelayStateModifier

from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON

from .conftest import MockLcnDeviceConnection, setup_platform

from tests.async_mock import call, patch


@patch.object(MockLcnDeviceConnection, "activate_status_request_handler")
async def test_setup_lcn_switch(activate_status_request_handler, hass, entry):
    """Test the setup of switch."""
    await setup_platform(hass, entry, DOMAIN_SWITCH)
    device_connection = get_device_connection(hass, "m000007", entry)
    assert device_connection
    calls = [
        call(OutputPort.OUTPUT1),
        call(OutputPort.OUTPUT2),
        call(RelayPort.RELAY1),
        call(RelayPort.RELAY2),
    ]
    activate_status_request_handler.assert_has_awaits(calls, any_order=True)
    assert activate_status_request_handler.await_count == 4


async def test_entity_attributes(hass, entry):
    """Test the attributes of an entity."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    await setup_platform(hass, entry, DOMAIN_SWITCH)

    entity_output = entity_registry.async_get("switch.switch_output1")

    assert entity_output
    assert entity_output.unique_id == f"{entry.entry_id}-m000007-output1"
    assert entity_output.original_name == "Switch_Output1"

    entity_relay = entity_registry.async_get("switch.switch_relay1")

    assert entity_relay
    assert entity_relay.unique_id == f"{entry.entry_id}-m000007-relay1"
    assert entity_relay.original_name == "Switch_Relay1"


@patch.object(MockLcnDeviceConnection, "dim_output")
async def test_output_turn_on(dim_output, hass, entry):
    """Test the output switch turns on."""
    await setup_platform(hass, entry, DOMAIN_SWITCH)

    # command failed
    dim_output.return_value = False

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switch_output1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    dim_output.assert_awaited_with(0, 100, 0)

    state = hass.states.get("switch.switch_output1")
    assert state is not None
    assert state.state != "on"

    # command success
    dim_output.reset_mock(return_value=True)
    dim_output.return_value = True

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switch_output1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    dim_output.assert_awaited_with(0, 100, 0)

    state = hass.states.get("switch.switch_output1")
    assert state is not None
    assert state.state == "on"


@patch.object(MockLcnDeviceConnection, "dim_output")
async def test_output_turn_off(dim_output, hass, entry):
    """Test the output switch turns off."""
    await setup_platform(hass, entry, DOMAIN_SWITCH)

    state = hass.states.get("switch.switch_output1")
    state.state = "on"

    # command failed
    dim_output.return_value = False

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switch_output1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    dim_output.assert_awaited_with(0, 0, 0)

    state = hass.states.get("switch.switch_output1")
    assert state is not None
    assert state.state != "off"

    # command success
    dim_output.reset_mock(return_value=True)
    dim_output.return_value = True

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switch_output1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    dim_output.assert_awaited_with(0, 0, 0)

    state = hass.states.get("switch.switch_output1")
    assert state is not None
    assert state.state == "off"


@patch.object(MockLcnDeviceConnection, "control_relays")
async def test_relay_turn_on(control_relays, hass, entry):
    """Test the relay switch turns on."""
    await setup_platform(hass, entry, DOMAIN_SWITCH)

    states = [RelayStateModifier.NOCHANGE] * 8
    states[0] = RelayStateModifier.ON

    # command failed
    control_relays.return_value = False

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switch_relay1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_relays.assert_awaited_with(states)

    state = hass.states.get("switch.switch_relay1")
    assert state is not None
    assert state.state != "on"

    # command success
    control_relays.reset_mock(return_value=True)
    control_relays.return_value = True

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switch_relay1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_relays.assert_awaited_with(states)

    state = hass.states.get("switch.switch_relay1")
    assert state is not None
    assert state.state == "on"


@patch.object(MockLcnDeviceConnection, "control_relays")
async def test_relay_turn_off(control_relays, hass, entry):
    """Test the output switch turns off successfully."""
    await setup_platform(hass, entry, DOMAIN_SWITCH)

    states = [RelayStateModifier.NOCHANGE] * 8
    states[0] = RelayStateModifier.OFF

    state = hass.states.get("switch.switch_relay1")
    state.state = "on"

    # command failed
    control_relays.return_value = False

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switch_relay1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_relays.assert_awaited_with(states)

    state = hass.states.get("switch.switch_relay1")
    assert state is not None
    assert state.state != "off"

    # command success
    control_relays.reset_mock(return_value=True)
    control_relays.return_value = True

    await hass.services.async_call(
        DOMAIN_SWITCH,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switch_relay1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_relays.assert_awaited_with(states)

    state = hass.states.get("switch.switch_relay1")
    assert state is not None
    assert state.state == "off"
