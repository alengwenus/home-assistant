"""Test helpers for the LCN integration."""
import pytest

from homeassistant.components.lcn import DOMAIN, helpers
from homeassistant.components.lcn.const import CONNECTION
from homeassistant.const import CONF_DEVICES

from .conftest import MockPchkConnectionManager, init_integration

from tests.async_mock import patch


def test_get_device_config(entry):
    """Test get_device_config."""
    # success
    device_config = helpers.get_device_config((0, 7, False), entry)
    assert device_config
    assert device_config in entry.data[CONF_DEVICES]

    # failure
    assert helpers.get_device_config("m000010", entry) is None


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_get_device_connection(hass, entry):
    """Test get_device_connection."""
    await init_integration(hass, entry)
    # success
    device_connection = helpers.get_device_connection(hass, (0, 7, False), entry)
    assert device_connection
    assert (
        device_connection
        in hass.data[DOMAIN][entry.entry_id][CONNECTION].address_conns.values()
    )

    # failure
    assert helpers.get_device_connection(hass, "m000010", entry) is None


def test_get_ressource_fails():
    """Test for failed get_ressource."""
    with pytest.raises(ValueError):
        helpers.get_resource("non_existing", {})
