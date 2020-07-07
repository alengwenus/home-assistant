"""Tests for LCN config flow."""
import pypck

from homeassistant import data_entry_flow
from homeassistant.components.lcn.const import (
    CONF_DIM_MODE,
    CONF_SK_NUM_TRIES,
    DOMAIN as DOMAIN_LCN,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.async_mock import patch

USER_INPUT = {
    CONF_HOST: "pchk",
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: 4114,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_SK_NUM_TRIES: 0,
    CONF_DIM_MODE: "STEPS200",
}


async def test_flow_manual_configuration(hass):
    """Test that config flow works with manual configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN_LCN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("homeassistant.components.lcn.config_flow._validate_connection"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_HOST]
    assert result["data"] == {
        CONF_IP_ADDRESS: USER_INPUT[CONF_IP_ADDRESS],
        CONF_PORT: USER_INPUT[CONF_PORT],
        CONF_USERNAME: USER_INPUT[CONF_USERNAME],
        CONF_PASSWORD: USER_INPUT[CONF_PASSWORD],
        CONF_SK_NUM_TRIES: USER_INPUT[CONF_SK_NUM_TRIES],
        CONF_DIM_MODE: USER_INPUT[CONF_DIM_MODE],
        CONF_DEVICES: [],
        CONF_ENTITIES: [],
    }


async def test_flow_fails_authentication_error(hass):
    """Test that config flow fails on authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN_LCN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lcn.config_flow._validate_connection",
        side_effect=pypck.connection.PchkAuthenticationError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == "abort"
    assert result["reason"] == "authentication_error"


async def test_flow_fails_license_error(hass):
    """Test that config flow fails on authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN_LCN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lcn.config_flow._validate_connection",
        side_effect=pypck.connection.PchkLicenseError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == "abort"
    assert result["reason"] == "license_error"


async def test_flow_fails_lcn_not_connected_error(hass):
    """Test that config flow fails on authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN_LCN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lcn.config_flow._validate_connection",
        side_effect=pypck.connection.PchkLcnNotConnectedError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == "abort"
    assert result["reason"] == "lcn_not_connected_error"


async def test_flow_fails_timeout_error(hass):
    """Test that config flow fails on authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN_LCN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lcn.config_flow._validate_connection",
        side_effect=TimeoutError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_timeout"
