"""Test init of LCN integration."""
import json

from pypck.connection import (
    PchkAuthenticationError,
    PchkConnectionManager,
    PchkLicenseError,
)

from homeassistant import config_entries
from homeassistant.components import lcn
from homeassistant.components.lcn.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import load_fixture
from tests.components.lcn import create_config_entry, init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry and unload of entry."""
    with patch.object(PchkConnectionManager, "async_connect"), patch.object(
        PchkConnectionManager, "get_address_conn"
    ):
        entry = await init_integration(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ENTRY_STATE_LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ENTRY_STATE_NOT_LOADED
        assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_update(hass):
    """Test a successful setup entry if entry with same id already exists."""
    with patch.object(PchkConnectionManager, "async_connect"), patch.object(
        PchkConnectionManager, "get_address_conn"
    ):
        # setup first entry
        entry = create_config_entry(hass)
        entry.source = config_entries.SOURCE_IMPORT

        # create dummy entity for LCN platform as an orphan
        entity_registry = await er.async_get_registry(hass)
        dummy_entity = entity_registry.async_get_or_create(
            "switch", DOMAIN, "dummy", config_entry=entry
        )
        assert dummy_entity in entity_registry.entities.values()

        # add entity to hass and setup (should cleanup dummy entity)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert dummy_entity not in entity_registry.entities.values()


async def test_async_setup_entry_raises_authentication_error(hass):
    """Test that an authentication error is handled properly."""
    with patch.object(
        PchkConnectionManager, "async_connect", side_effect=PchkAuthenticationError
    ):
        entry = await init_integration(hass)
    assert entry.state == ENTRY_STATE_SETUP_ERROR


async def test_async_setup_entry_raises_license_error(hass):
    """Test that an authentication error is handled properly."""
    with patch.object(
        PchkConnectionManager, "async_connect", side_effect=PchkLicenseError
    ):
        entry = await init_integration(hass)
    assert entry.state == ENTRY_STATE_SETUP_ERROR


async def test_async_setup_entry_raises_timeout_error(hass):
    """Test that an authentication error is handled properly."""
    with patch.object(PchkConnectionManager, "async_connect", side_effect=TimeoutError):
        entry = await init_integration(hass)
    assert entry.state == ENTRY_STATE_SETUP_ERROR


async def test_async_setup(hass):
    """Test a successful setup using data from configuration.yaml."""
    await async_setup_component(hass, "persistent_notification", {})

    config = json.loads(load_fixture("lcn/config.json"))
    with patch(
        "homeassistant.components.lcn.async_setup_entry", return_value=True
    ) as async_setup_entry:
        await lcn.async_setup(hass, config)
        await hass.async_block_till_done()

        assert async_setup_entry.await_count == 2


# print(async_setup_entry.await_args_list)


# assert False

# state = hass.states.get("light.light_output1")
# assert state == "Hallo"
# assert state is not None
# assert state.state != STATE_UNAVAILABLE
# assert state.state == "sunny"
