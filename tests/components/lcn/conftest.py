"""Test configuration and mocks for LCN component."""
import json

from pypck.connection import PchkConnectionManager
import pytest

from homeassistant.components.lcn.const import DOMAIN

from tests.async_mock import AsyncMock, Mock
from tests.common import MockConfigEntry, load_fixture


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

    get_address_conn = Mock()
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
    # entry = create_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
