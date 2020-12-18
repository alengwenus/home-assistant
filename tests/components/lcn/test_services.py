"""Test for the LCN services."""
import pypck
import pytest

from homeassistant.components.lcn import DOMAIN
from homeassistant.setup import async_setup_component

from .conftest import MockModuleConnection, MockPchkConnectionManager, setup_component

from tests.async_mock import patch


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "dim_output")
async def test_service_output_abs(dim_output, hass):
    """Test output_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "output_abs",
        {
            "address": "pchk.s0.m7",
            "output": "output1",
            "brightness": 100,
            "transition": 5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    dim_output.assert_awaited_with(0, 100, 9)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "rel_output")
async def test_service_output_rel(rel_output, hass):
    """Test output_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "output_rel",
        {
            "address": "pchk.s0.m7",
            "output": "output1",
            "brightness": 25,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    rel_output.assert_awaited_with(0, 25)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "toggle_output")
async def test_service_output_toggle(toggle_output, hass):
    """Test output_toggle service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "output_toggle",
        {
            "address": "pchk.s0.m7",
            "output": "output1",
            "transition": 5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    toggle_output.assert_awaited_with(0, 9)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "control_relays")
async def test_service_relays(control_relays, hass):
    """Test relays service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "relays",
        {"address": "pchk.s0.m7", "state": "0011TT--"},
        blocking=True,
    )
    await hass.async_block_till_done()

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    relay_states = [pypck.lcn_defs.RelayStateModifier[state] for state in states]

    control_relays.assert_awaited_with(relay_states)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "control_led")
async def test_service_led(control_relays, hass):
    """Test led service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "led",
        {"address": "pchk.s0.m7", "led": "led6", "state": "blink"},
        blocking=True,
    )
    await hass.async_block_till_done()

    led = pypck.lcn_defs.LedPort["LED6"]
    led_state = pypck.lcn_defs.LedStatus["BLINK"]

    control_relays.assert_awaited_with(led, led_state)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "var_abs")
async def test_service_var_abs(var_abs, hass):
    """Test var_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "var_abs",
        {
            "address": "pchk.s0.m7",
            "variable": "var1",
            "value": 75,
            "unit_of_measurement": "%",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    var_abs.assert_awaited_with(
        pypck.lcn_defs.Var["VAR1"], 75, pypck.lcn_defs.VarUnit.parse("%")
    )


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "var_rel")
async def test_service_var_rel(var_rel, hass):
    """Test var_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "var_rel",
        {
            "address": "pchk.s0.m7",
            "variable": "var1",
            "value": 10,
            "unit_of_measurement": "%",
            "value_reference": "current",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    var_rel.assert_awaited_with(
        pypck.lcn_defs.Var["VAR1"],
        10,
        pypck.lcn_defs.VarUnit.parse("%"),
        pypck.lcn_defs.RelVarRef["CURRENT"],
    )


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "var_reset")
async def test_service_var_reset(var_reset, hass):
    """Test var_reset service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "var_reset",
        {"address": "pchk.s0.m7", "variable": "var1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    var_reset.assert_awaited_with(pypck.lcn_defs.Var["VAR1"])


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "lock_regulator")
async def test_service_lock_regulator(lock_regulator, hass):
    """Test lock_regulator service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "lock_regulator",
        {"address": "pchk.s0.m7", "setpoint": "r1varsetpoint", "state": True},
        blocking=True,
    )
    await hass.async_block_till_done()

    lock_regulator.assert_awaited_with(0, True)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "send_keys")
async def test_service_send_keys(send_keys, hass):
    """Test send_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "send_keys",
        {"address": "pchk.s0.m7", "keys": "a1a5d8", "state": "hit"},
        blocking=True,
    )
    await hass.async_block_till_done()

    keys = [[False] * 8 for i in range(4)]
    keys[0][0] = True
    keys[0][4] = True
    keys[3][7] = True

    send_keys.assert_awaited_with(keys, pypck.lcn_defs.SendKeyCommand["HIT"])


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "send_keys_hit_deferred")
async def test_service_send_keys_hit_deferred(send_keys_hit_deferred, hass):
    """Test send_keys (hit_deferred) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    keys = [[False] * 8 for i in range(4)]
    keys[0][0] = True
    keys[0][4] = True
    keys[3][7] = True

    # success
    await hass.services.async_call(
        DOMAIN,
        "send_keys",
        {"address": "pchk.s0.m7", "keys": "a1a5d8", "time": 5, "time_unit": "s"},
        blocking=True,
    )
    await hass.async_block_till_done()

    send_keys_hit_deferred.assert_awaited_with(
        keys, 5, pypck.lcn_defs.TimeUnit.parse("S")
    )

    # wrong key action
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            "send_keys",
            {
                "address": "pchk.s0.m7",
                "keys": "a1a5d8",
                "state": "make",
                "time": 5,
                "time_unit": "s",
            },
            blocking=True,
        )
        await hass.async_block_till_done()


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "lock_keys")
async def test_service_lock_keys(lock_keys, hass):
    """Test lock_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "lock_keys",
        {"address": "pchk.s0.m7", "table": "a", "state": "0011TT--"},
        blocking=True,
    )
    await hass.async_block_till_done()

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]
    lock_keys.assert_awaited_with(0, lock_states)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "lock_keys_tab_a_temporary")
async def test_service_lock_keys_tab_a_temporary(lock_keys_tab_a_temporary, hass):
    """Test lock_keys (tab_a_temporary) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]

    # success
    await hass.services.async_call(
        DOMAIN,
        "lock_keys",
        {"address": "pchk.s0.m7", "state": "0011TT--", "time": 10, "time_unit": "s"},
        blocking=True,
    )
    await hass.async_block_till_done()

    lock_keys_tab_a_temporary.assert_awaited_with(
        10, pypck.lcn_defs.TimeUnit.parse("S"), lock_states
    )

    # wrong table
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            "lock_keys",
            {
                "address": "pchk.s0.m7",
                "table": "b",
                "state": "0011TT--",
                "time": 10,
                "time_unit": "s",
            },
            blocking=True,
        )
        await hass.async_block_till_done()


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "dyn_text")
async def test_service_dyn_text(dyn_text, hass):
    """Test dyn_text service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "dyn_text",
        {"address": "pchk.s0.m7", "row": 1, "text": "text in row 1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    dyn_text.assert_awaited_with(0, "text in row 1")


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "pck")
async def test_service_pck(pck, hass):
    """Test pck service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    await hass.services.async_call(
        DOMAIN,
        "pck",
        {"address": "pchk.s0.m7", "pck": "PIN4"},
        blocking=True,
    )
    await hass.async_block_till_done()

    pck.assert_awaited_with("PIN4")


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
@patch.object(MockModuleConnection, "pck")
async def test_service_called_with_invalid_host_id(pck, hass):
    """Test service was called with non existing host id."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            "pck",
            {"address": "foobar.s0.m7", "pck": "PIN4"},
            blocking=True,
        )
        await hass.async_block_till_done()

    pck.assert_not_awaited()
