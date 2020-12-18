"""Test configuration and mocks for LCN component."""
import json

import pypck
from pypck.connection import PchkConnectionManager
import pypck.module
from pypck.module import GroupConnection, ModuleConnection
import pytest

from homeassistant.components.lcn.const import (
    CONF_DIM_MODE,
    CONF_SK_NUM_TRIES,
    CONNECTION,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry, load_fixture


class MockModuleConnection(ModuleConnection):
    """Fake a LCN module connection."""

    status_request_handler = AsyncMock()
    activate_status_request_handler = AsyncMock()
    cancel_status_request_handler = AsyncMock()
    send_command = AsyncMock(return_value=True)


class MockGroupConnection(GroupConnection):
    """Fake a LCN group connection."""

    send_command = AsyncMock(return_value=True)


class MockPchkConnectionManager(PchkConnectionManager):
    """Fake connection handler."""

    async def async_connect(self, timeout=30):
        """Mock establishing a connection to PCHK."""
        self.authentication_completed_future.set_result(True)
        self.license_error_future.set_result(True)
        self.segment_scan_completed_event.set()

    async def async_close(self):
        """Mock closing a connection to PCHK."""
        pass

    @patch.object(pypck.connection, "ModuleConnection", MockModuleConnection)
    @patch.object(pypck.connection, "GroupConnection", MockGroupConnection)
    def get_address_conn(self, addr):
        """Get LCN address connection."""
        return super().get_address_conn(addr, request_serials=False)

    send_command = AsyncMock()


def create_config_entry(name):
    """Set up config entries with configuration data."""
    fixture_filename = f"lcn/config_entry_{name}.json"
    entry_data = json.loads(load_fixture(fixture_filename))
    options = {}

    title = entry_data[CONF_HOST]
    unique_id = fixture_filename
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=unique_id,
        data=entry_data,
        options=options,
    )
    return entry


@pytest.fixture(name="entry")
def create_config_entry_pchk():
    """Return one specific config entry."""
    return create_config_entry("pchk")


@pytest.fixture(name="entry2")
def create_config_entry_myhome():
    """Return one specific config entry."""
    return create_config_entry("myhome")


async def init_integration(hass, entry):
    """Set up the LCN integration in Home Assistant."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def setup_platform(hass, entry, platform):
    """Set up the LCN platform."""
    hass.config.components.add(entry.domain)
    settings = {
        "SK_NUMN_TRIES": entry.data[CONF_SK_NUM_TRIES],
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[entry.data[CONF_DIM_MODE]],
    }
    lcn_connection = MockPchkConnectionManager(
        entry.data[CONF_IP_ADDRESS],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        settings=settings,
        connection_id=entry.title,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {CONNECTION: lcn_connection})
    await hass.config_entries.async_forward_entry_setup(entry, platform)
    await hass.async_block_till_done()


async def setup_component(hass):
    """Set up the LCN component."""
    fixture_filename = "lcn/config.json"
    config_data = json.loads(load_fixture(fixture_filename))

    await async_setup_component(hass, DOMAIN, config_data)
    await hass.async_block_till_done()
