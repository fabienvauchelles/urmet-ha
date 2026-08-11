"""The Urmet doorphone integration (DESIGN 6).

``async_setup_entry`` builds the gateway client and the push coordinator, seeds
the first snapshot through ``async_config_entry_first_refresh`` (so a cold gateway
raises ``ConfigEntryNotReady`` and Home Assistant retries), then opens the event
WebSocket and stores both on ``entry.runtime_data``.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .client import GatewayClient
from .const import CONF_HOST, CONF_PORT, DOMAIN, LOGGER
from .coordinator import (
    UrmetConfigEntry,
    UrmetCoordinator,
    UrmetRuntimeData,
)
from .repairs import async_attach_issue_monitor
from .services import async_setup_services, async_unload_services
from .websocket_api import async_register_websocket_api

# The entity platforms (DESIGN 6.3). WP9 owns the card and the WebSocket API and
# registers those in ``async_setup`` above, so they are not platforms here.
PLATFORMS: list[Platform] = [
    Platform.EVENT,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

# The card the WebSocket API serves the frontend (DESIGN 6.2, 7). CI writes the
# built bundle to www/ on release; a source checkout carries a placeholder.
CARD_FILENAME = "urmet-portier-card.js"
CARD_URL = f"/urmet/{CARD_FILENAME}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the card and its WebSocket API once per Home Assistant instance."""
    async_register_websocket_api(hass)
    await _register_card(hass)
    return True


async def _register_card(hass: HomeAssistant) -> None:
    """Serve the card bundle and load it as a frontend module (DESIGN 6.2)."""
    card = str(Path(__file__).parent / "www" / CARD_FILENAME)
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, card, True)])
    # add_extra_js_url needs the frontend integration, an after-dependency that is
    # always present on a running instance but may be absent in a bare test loop.
    if DATA_EXTRA_MODULE_URL in hass.data:
        add_extra_js_url(hass, CARD_URL)
    else:
        LOGGER.debug("frontend not loaded, urmet card static path served but not auto-added")


async def async_setup_entry(hass: HomeAssistant, entry: UrmetConfigEntry) -> bool:
    """Set up an Urmet doorphone from a config entry."""
    client = GatewayClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = UrmetCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    await client.async_start()
    entry.runtime_data = UrmetRuntimeData(client=client, coordinator=coordinator)
    entry.async_on_unload(async_attach_issue_monitor(hass, entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UrmetConfigEntry) -> bool:
    """Tear down the platforms, drop the coordinator listeners, stop the client."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = entry.runtime_data
        data.coordinator.async_release()
        await data.client.async_stop()
        others = [
            other
            for other in hass.config_entries.async_loaded_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ]
        if not others:
            async_unload_services(hass)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: UrmetConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
