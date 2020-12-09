"""Tests for LCN."""
import json

from homeassistant.components.lcn.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture


def create_config_entry(
    title="pchk", unique_id="0123456789abcdef0123456789abcdef"
) -> MockConfigEntry:
    """Set up config entry with configuration data."""
    data = json.loads(load_fixture("lcn/config_entry_data.json"))
    options = {}

    entry = MockConfigEntry(
        domain=DOMAIN, title=title, unique_id=unique_id, data=data[0], options=options
    )
    return entry


async def init_integration(hass) -> MockConfigEntry:
    """Set up the LCN integration in Home Assistant."""
    entry = create_config_entry(hass)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
