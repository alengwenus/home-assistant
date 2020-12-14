"""Test for the LCN scene platform."""
from pypck.lcn_defs import OutputPort, RelayPort

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON

from .conftest import MockLcnDeviceConnection, setup_platform

from tests.async_mock import patch


async def test_entity_attributes(hass, entry):
    """Test the attributes of an entity."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    await setup_platform(hass, entry, DOMAIN_SCENE)

    entity = entity_registry.async_get("scene.romantic")

    assert entity
    assert entity.unique_id == f"{entry.entry_id}-m000007-0.0"
    assert entity.original_name == "Romantic"

    entity_transition = entity_registry.async_get("scene.romantic_transition")

    assert entity_transition
    assert entity_transition.unique_id == f"{entry.entry_id}-m000007-0.1"
    assert entity_transition.original_name == "Romantic Transition"


@patch.object(MockLcnDeviceConnection, "activate_scene")
async def test_scene_activate(activate_scene, hass, entry):
    """Test the scene is activated."""
    await setup_platform(hass, entry, DOMAIN_SCENE)

    await hass.services.async_call(
        DOMAIN_SCENE,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.romantic"},
        blocking=True,
    )
    state = hass.states.get("scene.romantic")
    assert state.attributes["friendly_name"] == "Romantic"
    activate_scene.assert_awaited_with(
        0, 0, [OutputPort.OUTPUT1, OutputPort.OUTPUT2], [RelayPort.RELAY1], None
    )


async def test_unload_config_entry(hass, entry):
    """Test the scene is removed when the config entry is unloaded."""
    await setup_platform(hass, entry, DOMAIN_SCENE)
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_SCENE)
    assert not hass.states.get("scene.romantic")
