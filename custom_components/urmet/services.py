"""Actions and the shared command layer (DESIGN 6.5).

Every actuator and call command the integration issues goes through one of the
``async_*`` coroutines here, so the buttons, the switch and the ``urmet.*``
services all take the same path to the gateway. The buttons call these
coroutines underneath (DESIGN 6.3), and the service handlers are thin wrappers
that parse the call and format the response.

``urmet.open`` never claims success it did not get: any status other than the
gateway's ``204`` maps to ``acknowledged: false`` (unknown), never to "opened"
(DESIGN 5.2 failure table, 6.4). The open origin is stashed before the request so
the ``event.portier_ouverture`` entity can label the gateway ``open`` event it
receives back (card, service or notification).
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .client import GatewayClient, GatewayResponse
from .const import (
    ACTIVE_CALL_STATES,
    ACTUATOR_DOOR,
    ACTUATOR_GATE,
    DEFAULT_ORIGIN,
    DOMAIN,
    ORIGIN_SERVICE,
)
from .coordinator import UrmetConfigEntry
from .models import CallView

ACTUATORS = (ACTUATOR_DOOR, ACTUATOR_GATE)

SERVICE_ANSWER = "answer"
SERVICE_HANG_UP = "hang_up"
SERVICE_LOOK = "look"
SERVICE_OPEN = "open"
SERVICE_SET_MICROPHONE = "set_microphone"

ATTR_CALL_ID = "call_id"
ATTR_ACTUATOR = "actuator"
ATTR_WANT_VIDEO = "want_video"
ATTR_MUTED = "muted"
ATTR_ACKNOWLEDGED = "acknowledged"

_OPEN_PATHS = {ACTUATOR_DOOR: "/api/door/open", ACTUATOR_GATE: "/api/gate/open"}
_PENDING_OPEN_ORIGIN = f"{DOMAIN}_open_origin"


# --- Open-origin stash (read back by the event entity) ---------------------


@callback
def stash_open_origin(hass: HomeAssistant, entry_id: str, origin: str) -> None:
    """Record who initiated the next open so the event entity can label it."""
    hass.data.setdefault(_PENDING_OPEN_ORIGIN, {})[entry_id] = origin


@callback
def take_open_origin(hass: HomeAssistant, entry_id: str) -> str:
    """Consume the stashed origin for one gateway ``open`` event."""
    store: dict[str, str] = hass.data.get(_PENDING_OPEN_ORIGIN, {})
    return store.pop(entry_id, DEFAULT_ORIGIN)


# --- Command coroutines (the single path to the gateway) -------------------


async def async_open(
    hass: HomeAssistant,
    entry: UrmetConfigEntry,
    *,
    actuator: str,
    call_id: str | None,
    origin: str,
) -> bool:
    """Fire an actuator. Return whether the panel acknowledged (DESIGN 6.5)."""
    if actuator not in _OPEN_PATHS:
        raise ServiceValidationError(f"unknown actuator {actuator!r}")
    stash_open_origin(hass, entry.entry_id, origin)
    resp = await _client(entry).async_request(
        "POST", _OPEN_PATHS[actuator], json={ATTR_CALL_ID: call_id}
    )
    return resp.status == 204


async def async_answer(
    hass: HomeAssistant, entry: UrmetConfigEntry, *, call_id: str | None
) -> None:
    """Answer the named ring, or the only ringing dialog (DESIGN 6.5)."""
    target = call_id or _sole_call(entry, ("ringing",), "no ringing call to answer")
    _raise_for_status(await _client(entry).async_request("POST", f"/api/call/{target}/answer"))


async def async_hang_up(
    hass: HomeAssistant, entry: UrmetConfigEntry, *, call_id: str | None
) -> None:
    """Hang up a call. A no-op when nothing is live (DESIGN 6.5, idempotent)."""
    target = call_id or _first_active_call(entry)
    if target is None:
        return
    _raise_for_status(await _client(entry).async_request("DELETE", f"/api/call/{target}"))


async def async_look(
    hass: HomeAssistant, entry: UrmetConfigEntry, *, want_video: bool
) -> ServiceResponse:
    """Place an on-demand call and return its id (DESIGN 6.5)."""
    resp = await _client(entry).async_request(
        "POST", "/api/call", json={ATTR_WANT_VIDEO: want_video}
    )
    if resp.status != 201:
        _raise_for_status(resp)
    return {ATTR_CALL_ID: str(resp.body.get(ATTR_CALL_ID, ""))}


async def async_set_microphone(
    hass: HomeAssistant, entry: UrmetConfigEntry, *, muted: bool
) -> None:
    """Mute or unmute the browser-to-panel microphone (DESIGN 6.5)."""
    _raise_for_status(
        await _client(entry).async_request("POST", "/api/mic", json={ATTR_MUTED: muted})
    )


# --- Resolution helpers ----------------------------------------------------


def _client(entry: UrmetConfigEntry) -> GatewayClient:
    return entry.runtime_data.client


def _calls(entry: UrmetConfigEntry) -> tuple[CallView, ...]:
    data = entry.runtime_data.coordinator.data
    return data.calls if data is not None else ()


def _sole_call(entry: UrmetConfigEntry, states: tuple[str, ...], msg: str) -> str:
    matches = [c.id for c in _calls(entry) if c.state in states]
    if len(matches) == 1:
        return matches[0]
    raise ServiceValidationError(msg if not matches else f"{msg}: several match")


def _first_active_call(entry: UrmetConfigEntry) -> str | None:
    for call in _calls(entry):
        if call.state in ACTIVE_CALL_STATES:
            return call.id
    return None


def _raise_for_status(resp: GatewayResponse) -> None:
    if resp.status < 400:
        return
    name = str(resp.body.get("error", "GatewayError"))
    detail = str(resp.body.get("detail", f"gateway returned {resp.status}"))
    raise HomeAssistantError(f"{name}: {detail}")


def _resolve_entry(hass: HomeAssistant) -> UrmetConfigEntry:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("no Urmet doorphone is set up")
    return entries[0]


# --- Service handlers ------------------------------------------------------


async def _handle_open(call: ServiceCall) -> ServiceResponse:
    entry = _resolve_entry(call.hass)
    acknowledged = await async_open(
        call.hass,
        entry,
        actuator=call.data[ATTR_ACTUATOR],
        call_id=call.data.get(ATTR_CALL_ID),
        origin=ORIGIN_SERVICE,
    )
    return {ATTR_ACKNOWLEDGED: acknowledged}


async def _handle_answer(call: ServiceCall) -> None:
    entry = _resolve_entry(call.hass)
    await async_answer(call.hass, entry, call_id=call.data.get(ATTR_CALL_ID))


async def _handle_hang_up(call: ServiceCall) -> None:
    entry = _resolve_entry(call.hass)
    await async_hang_up(call.hass, entry, call_id=call.data.get(ATTR_CALL_ID))


async def _handle_look(call: ServiceCall) -> ServiceResponse:
    entry = _resolve_entry(call.hass)
    return await async_look(call.hass, entry, want_video=call.data[ATTR_WANT_VIDEO])


async def _handle_set_microphone(call: ServiceCall) -> None:
    entry = _resolve_entry(call.hass)
    await async_set_microphone(call.hass, entry, muted=call.data[ATTR_MUTED])


_CALL_ID_FIELD = {vol.Optional(ATTR_CALL_ID): selector.TextSelector()}
_ANSWER_SCHEMA = vol.Schema(_CALL_ID_FIELD)
_HANG_UP_SCHEMA = vol.Schema(_CALL_ID_FIELD)
_LOOK_SCHEMA = vol.Schema({vol.Optional(ATTR_WANT_VIDEO, default=True): selector.BooleanSelector()})
_OPEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ACTUATOR): vol.In(ACTUATORS),
        vol.Optional(ATTR_CALL_ID): selector.TextSelector(),
    }
)
_SET_MICROPHONE_SCHEMA = vol.Schema({vol.Required(ATTR_MUTED): cv.boolean})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the ``urmet.*`` actions once for the integration."""
    if hass.services.has_service(DOMAIN, SERVICE_OPEN):
        return
    hass.services.async_register(DOMAIN, SERVICE_ANSWER, _handle_answer, schema=_ANSWER_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_HANG_UP, _handle_hang_up, schema=_HANG_UP_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOOK,
        _handle_look,
        schema=_LOOK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN,
        _handle_open,
        schema=_OPEN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MICROPHONE,
        _handle_set_microphone,
        schema=_SET_MICROPHONE_SCHEMA,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the actions when the last entry unloads."""
    for name in (
        SERVICE_ANSWER,
        SERVICE_HANG_UP,
        SERVICE_LOOK,
        SERVICE_OPEN,
        SERVICE_SET_MICROPHONE,
    ):
        hass.services.async_remove(DOMAIN, name)
