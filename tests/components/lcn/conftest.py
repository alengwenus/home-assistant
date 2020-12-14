"""Test configuration and mocks for LCN component."""
import json

import pypck
from pypck.connection import PchkConnectionManager
from pypck.module import ModuleConnection
import pytest

from homeassistant.components.lcn.const import (
    CONF_DIM_MODE,
    CONF_SK_NUM_TRIES,
    CONNECTION,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from tests.async_mock import AsyncMock
from tests.common import MockConfigEntry, load_fixture


class MockLcnDeviceConnection(ModuleConnection):
    """Fake a LCN device connection."""

    activate_status_request_handler = AsyncMock()
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

    def get_address_conn(self, addr):
        """Get LCN address connection."""
        return MockLcnDeviceConnection(self, addr)

    send_command = AsyncMock()


@pytest.fixture(name="entry")
def create_config_entry() -> MockConfigEntry:
    """Set up config entry with configuration data."""
    data = json.loads(load_fixture("lcn/config_entry_data.json"))
    options = {}

    title = "pchk"
    unique_id = "0123456789abcdef0123456789abcdef"

    entry = MockConfigEntry(
        domain=DOMAIN, title=title, unique_id=unique_id, data=data[0], options=options
    )
    return entry


async def init_integration(hass, entry) -> MockConfigEntry:
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
    return entry
