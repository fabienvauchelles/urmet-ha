"""Service and actuator behaviour (DESIGN 6.5, recon 13 safe-opener).

The load-bearing case: ``urmet.open`` returns ``acknowledged: false`` on a 502
and the ``event.portier_ouverture`` entity never says "opened". An unacknowledged
open means the outcome is unknown, never that the door stayed shut and never that
it opened.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from gateway_double import DOORPHONE_MAC, FakeGateway
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.urmet.const import CONF_HOST, CONF_PORT, DOMAIN


async def _setup(hass: HomeAssistant, gateway: FakeGateway) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: gateway.host, CONF_PORT: gateway.port},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _id_for(hass: HomeAssistant, entry: MockConfigEntry, suffix: str) -> str:
    registry = er.async_get(hass)
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg.unique_id == f"{DOORPHONE_MAC}_{suffix}":
            return reg.entity_id
    raise AssertionError(f"no entity for suffix {suffix}")


async def _wait_until(
    hass: HomeAssistant, predicate: Callable[[], bool], timeout: float = 5.0
) -> None:
    deadline = hass.loop.time() + timeout
    while hass.loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition was not met within the timeout")


async def test_open_502_is_unacknowledged_and_never_opens(
    hass: HomeAssistant, fake_gateway: FakeGateway
) -> None:
    fake_gateway.open_status = 502
    entry = await _setup(hass, fake_gateway)
    actuator = _id_for(hass, entry, "actuator")
    door_total = _id_for(hass, entry, "door_total")

    response = await hass.services.async_call(
        DOMAIN,
        "open",
        {"actuator": "door"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert response == {"acknowledged": False}
    # The panel never acknowledged, so the event entity never fired.
    assert hass.states.get(actuator).state == STATE_UNKNOWN
    # And an unknown open is not counted as an opening.
    assert hass.states.get(door_total).state == "0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_open_204_fires_event_and_counts(
    hass: HomeAssistant, fake_gateway: FakeGateway
) -> None:
    entry = await _setup(hass, fake_gateway)
    actuator = _id_for(hass, entry, "actuator")
    door_total = _id_for(hass, entry, "door_total")

    caller = Context(user_id="user-abc")
    response = await hass.services.async_call(
        DOMAIN,
        "open",
        {"actuator": "door"},
        blocking=True,
        return_response=True,
        context=caller,
    )
    assert response == {"acknowledged": True}

    await _wait_until(hass, lambda: hass.states.get(actuator).state != STATE_UNKNOWN)
    state = hass.states.get(actuator)
    assert state.attributes["event_type"] == "door"
    assert state.attributes["acknowledged"] is True
    assert state.attributes["origin"] == "service"
    # The open is attributed to the user who asked, so the logbook can name them.
    assert state.context.user_id == "user-abc"

    await _wait_until(hass, lambda: hass.states.get(door_total).state == "1")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_microphone_switch(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = await _setup(hass, fake_gateway)
    mic = _id_for(hass, entry, "mic")
    assert hass.states.get(mic).state == STATE_OFF

    await hass.services.async_call("switch", "turn_on", {"entity_id": mic}, blocking=True)
    await _wait_until(hass, lambda: hass.states.get(mic).state == STATE_ON)
    assert fake_gateway.mic_muted is False

    await hass.services.async_call("switch", "turn_off", {"entity_id": mic}, blocking=True)
    await _wait_until(hass, lambda: hass.states.get(mic).state == STATE_OFF)
    assert fake_gateway.mic_muted is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_look_returns_call_id(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = await _setup(hass, fake_gateway)
    response = await hass.services.async_call(
        DOMAIN, "look", {}, blocking=True, return_response=True
    )
    assert response == {"call_id": "call-1"}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_answer_resolves_the_only_ringing_call(
    hass: HomeAssistant, fake_gateway: FakeGateway
) -> None:
    fake_gateway.calls = [{"id": "call-1", "state": "ringing", "direction": "inbound"}]
    entry = await _setup(hass, fake_gateway)
    coordinator = entry.runtime_data.coordinator
    await _wait_until(hass, lambda: coordinator.data is not None and bool(coordinator.data.calls))

    # A ringing call is present, so answer with no id resolves it without error.
    await hass.services.async_call(DOMAIN, "answer", {}, blocking=True)

    # With no ringing call, answer refuses rather than guessing.
    fake_gateway.calls = []
    await fake_gateway.push_state()
    await _wait_until(hass, lambda: coordinator.data is not None and not coordinator.data.calls)
    try:
        await hass.services.async_call(DOMAIN, "answer", {}, blocking=True)
        raise AssertionError("answer should refuse when nothing is ringing")
    except ServiceValidationError:
        pass

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
