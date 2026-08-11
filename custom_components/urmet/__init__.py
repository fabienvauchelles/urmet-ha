"""The Urmet doorphone integration (DESIGN 6).

``async_setup_entry`` builds the gateway client and the push coordinator, seeds
the first snapshot through ``async_config_entry_first_refresh`` (so a cold gateway
raises ``ConfigEntryNotReady`` and Home Assistant retries), then opens the event
WebSocket and stores both on ``entry.runtime_data``.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import CONF_RESOURCE_TYPE_WS
from homeassistant.components.lovelace.const import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_when_setup

from .client import GatewayClient
from .const import CONF_HOST, CONF_PORT, DOMAIN, LOGGER
from .coordinator import (
    UrmetConfigEntry,
    UrmetCoordinator,
    UrmetRuntimeData,
)
from .repairs import async_attach_issue_monitor
from .services import async_setup_services
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
    """Register the card, its WebSocket API and the actions, once per instance."""
    async_register_websocket_api(hass)
    async_setup_services(hass)
    await _register_card(hass)
    return True


async def _register_card(hass: HomeAssistant) -> None:
    """Serve the card bundle and register it as a Lovelace resource (DESIGN 6.2).

    The bundle loads as a Lovelace resource rather than through
    ``add_extra_js_url``: that helper injects the module during the initial page
    parse, before the frontend installs its scoped custom-element registry, so
    the card would define itself into a registry Home Assistant no longer reads
    and the tag would render as "custom element doesn't exist". A resource is
    imported after that registry is in place, which is where the built-in cards
    that work live too.
    """
    card = str(Path(__file__).parent / "www" / CARD_FILENAME)
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, card, True)])
    async_when_setup(hass, "lovelace", _register_card_resource)


async def _register_card_resource(hass: HomeAssistant, _component: str) -> None:
    """Add or refresh the card's Lovelace resource, versioned to bust the cache.

    Only storage-mode dashboards accept a programmatic resource, which is exactly
    a ``ResourceStorageCollection``; a YAML-mode instance keeps its resources in
    the file and must add the URL by hand, so this logs and returns there.
    """
    data = hass.data.get(LOVELACE_DOMAIN)
    resources = getattr(data, "resources", None)
    if not isinstance(resources, ResourceStorageCollection):
        LOGGER.debug("lovelace is not in storage mode; add the urmet card resource by hand")
        return
    integration = await async_get_integration(hass, DOMAIN)
    versioned = f"{CARD_URL}?v={integration.version}"
    # Force the store to load before reading it. async_get_info gained a return
    # annotation after the pinned Home Assistant, so the typed context flags it.
    await resources.async_get_info()  # type: ignore[no-untyped-call]
    for item in resources.async_items():
        if str(item.get(CONF_URL, "")).split("?", 1)[0] != CARD_URL:
            continue
        if item[CONF_URL] != versioned:
            await resources.async_update_item(item["id"], {CONF_URL: versioned})
        return
    await resources.async_create_item({CONF_RESOURCE_TYPE_WS: "module", CONF_URL: versioned})


async def async_setup_entry(hass: HomeAssistant, entry: UrmetConfigEntry) -> bool:
    """Set up an Urmet doorphone from a config entry."""
    client = GatewayClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = UrmetCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    await client.async_start()
    entry.runtime_data = UrmetRuntimeData(client=client, coordinator=coordinator)
    entry.async_on_unload(async_attach_issue_monitor(entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UrmetConfigEntry) -> bool:
    """Tear down the platforms, drop the coordinator listeners, stop the client."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = entry.runtime_data
        data.coordinator.async_release()
        await data.client.async_stop()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: UrmetConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
