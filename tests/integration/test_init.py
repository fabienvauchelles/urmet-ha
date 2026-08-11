"""Setup, teardown and reconnection scenarios (DESIGN 6.2)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import pytest
from gateway_double import DOORPHONE_MAC, FakeGateway
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.urmet import client as client_module
from custom_components.urmet.const import CONF_HOST, CONF_PORT, DOMAIN


def _entry(gateway: FakeGateway) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: gateway.host, CONF_PORT: gateway.port},
    )


async def _wait_until(
    hass: HomeAssistant, predicate: Callable[[], bool], timeout: float = 5.0
) -> None:
    deadline = hass.loop.time() + timeout
    while hass.loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition was not met within the timeout")


async def test_setup_and_unload(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = _entry(fake_gateway)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert coordinator.data.registered is True
    assert coordinator.data.doorphone is not None
    assert coordinator.data.doorphone.mac == DOORPHONE_MAC

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_cold_gateway_raises_not_ready(hass: HomeAssistant, dead_port: int) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: dead_port},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY

    # Cancel the pending retry so no timer lingers past the test.
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_gateway_restart_reconnects(
    hass: HomeAssistant,
    fake_gateway: FakeGateway,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Shrink the backoff so the reconnect window is milliseconds, not seconds.
    monkeypatch.setattr(client_module, "BACKOFF_SCHEDULE_S", (0.05,))
    entry = _entry(fake_gateway)
    entry.add_to_hass(hass)

    with caplog.at_level(logging.DEBUG, logger="custom_components.urmet"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data.coordinator
        assert coordinator.data is not None
        assert coordinator.data.registered is True

        # A gateway restart: stop it (the WebSocket drops), then bring it back on
        # the same port answering differently.
        fake_gateway.registered = False
        await fake_gateway.stop()
        await _wait_until(hass, lambda: coordinator.last_update_success is False)
        await fake_gateway.start()
        await _wait_until(
            hass,
            lambda: coordinator.data is not None and coordinator.data.registered is False,
        )

    assert coordinator.last_update_success is True

    reconnect_warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "reconnect" in record.getMessage()
    ]
    assert len(reconnect_warnings) == 1, "one log per backoff step, not per attempt"
    assert any(
        "reconnected" in record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
