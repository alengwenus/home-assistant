"""Tests for LCN component."""
from copy import deepcopy

import pypck

from homeassistant import config_entries
from homeassistant.components.lcn import (
    CONF_DIM_MODE,
    CONF_SK_NUM_TRIES,
    DOMAIN as DOMAIN_LCN,
)
from homeassistant.components.lcn.const import ADD_ENTITIES_CALLBACKS, CONNECTION
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: 4114,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_SK_NUM_TRIES: 0,
    CONF_DIM_MODE: "STEPS200",
    CONF_DEVICES: [],
    CONF_ENTITIES: [],
}

ENTRY_OPTIONS = {}


def setup_lcn_config_entry(
    hass,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    entry_id="1",
    source=config_entries.SOURCE_USER,
):
    """Setups a config_entry for LCN integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN_LCN,
        source=source,
        data=deepcopy(config),
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        options=deepcopy(options),
        entry_id=entry_id,
        title="pchk",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@patch(
    "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
    return_value=True,
)
@patch("pypck.connection.PchkConnectionManager")
async def test_setup_integration(lcn_connection, forward_entry_setup, hass):
    """Test setup of LCN integration."""
    entry = setup_lcn_config_entry(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    lcn_connection.assert_called()

    lcn_connection.assert_called_with(
        hass.loop,
        entry.data[CONF_IP_ADDRESS],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        settings={
            "SK_NUM_TRIES": entry.data[CONF_SK_NUM_TRIES],
            "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[entry.data[CONF_DIM_MODE]],
        },
        connection_id=entry.entry_id,
    )

    lcn_connection().async_connect.assert_called()

    assert DOMAIN_LCN in hass.data
    assert entry.entry_id in hass.data[DOMAIN_LCN]
    assert CONNECTION in hass.data[DOMAIN_LCN][entry.entry_id]
    assert hass.data[DOMAIN_LCN][entry.entry_id][ADD_ENTITIES_CALLBACKS] == {}

    assert forward_entry_setup.mock_calls[0][1] == (entry, "binary_sensor")
    assert forward_entry_setup.mock_calls[1][1] == (entry, "climate")
    assert forward_entry_setup.mock_calls[2][1] == (entry, "cover")
    assert forward_entry_setup.mock_calls[3][1] == (entry, "light")
    assert forward_entry_setup.mock_calls[4][1] == (entry, "scene")
    assert forward_entry_setup.mock_calls[5][1] == (entry, "sensor")
    assert forward_entry_setup.mock_calls[6][1] == (entry, "switch")

    assert result is True


async def test_setup_fails_authentication_error(hass):
    """Test setup fail due to authentication error."""
    entry = setup_lcn_config_entry(hass)
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect",
        side_effect=pypck.connection.PchkAuthenticationError(),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert result is False


async def test_setup_fails_license_error(hass):
    """Test setup fail due to license error."""
    entry = setup_lcn_config_entry(hass)
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect",
        side_effect=pypck.connection.PchkLicenseError(),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert result is False


async def test_setup_fails_lcn_not_connected_error(hass):
    """Test setup fail due to lcn not connected error."""
    entry = setup_lcn_config_entry(hass)
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect",
        side_effect=pypck.connection.PchkLcnNotConnectedError(),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert result is False


async def test_setup_fails_timeout_error(hass):
    """Test setup fail due to timeout error."""
    entry = setup_lcn_config_entry(hass)
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect",
        side_effect=TimeoutError(),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
