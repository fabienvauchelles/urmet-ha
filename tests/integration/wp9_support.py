"""Shared fixtures and helpers for the WP9 integration scenarios.

The ``gateway`` fixture is defined here and imported into each WP9 test module so
pytest registers it there (this directory already carries a WP7 ``conftest`` that
cannot host a second copy). Helpers set an entry up against the double and poll for
a condition, mirroring the wait pattern the existing scenarios use.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from webrtc_gateway import DOORPHONE_MAC, WebrtcGateway, free_tcp_port

from custom_components.urmet.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RING_COALESCE,
    CONF_SHOW_TECH,
    DOMAIN,
)

DEFAULT_OPTIONS = {CONF_RING_COALESCE: 5, CONF_SHOW_TECH: True}


@pytest.fixture
async def gateway(socket_enabled: None) -> AsyncIterator[WebrtcGateway]:
    """A started WP9 gateway double on a free loopback port."""
    double = WebrtcGateway(free_tcp_port())
    await double.start()
    yield double
    await double.stop()


async def setup_entry(
    hass: HomeAssistant,
    double: WebrtcGateway,
    *,
    options: dict[str, object] | None = None,
) -> MockConfigEntry:
    """Add and set up a loaded config entry pointing at ``double``."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Portier",
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: double.host, CONF_PORT: double.port},
        options=DEFAULT_OPTIONS if options is None else options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def wait_until(
    hass: HomeAssistant, predicate: Callable[[], bool], timeout: float = 5.0
) -> None:
    """Poll ``predicate`` until true, driving the loop, or fail on timeout."""
    deadline = hass.loop.time() + timeout
    while hass.loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition was not met within the timeout")
