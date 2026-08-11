"""The single path from Home Assistant to the gateway (DESIGN 6.5).

Every actuator and call command the integration issues goes through one of the
``async_*`` coroutines here, so the buttons, the switch and the ``urmet.*``
actions all take the same path. ``services.py`` parses the calls and formats the
responses; nothing else names a gateway path.

``urmet.open`` never claims success it did not get: any status other than the
gateway's ``204`` maps to ``acknowledged: false`` (unknown), never to "opened"
(DESIGN 5.2 failure table, 6.4). The open origin is stashed on the entry's
runtime data before the request, so the ``event.portier_ouverture`` entity can
label the gateway ``open`` event it receives back (card, service or notification).
"""

from __future__ import annotations

from homeassistant.core import Context, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .client import GatewayClient, GatewayResponse
from .const import ACTUATOR_DOOR, ACTUATOR_GATE, DEFAULT_ORIGIN
from .coordinator import PendingOpen, UrmetConfigEntry
from .models import CallState, CallView

ATTR_CALL_ID = "call_id"
ATTR_ACTUATOR = "actuator"
ATTR_WANT_VIDEO = "want_video"
ATTR_MUTED = "muted"
ATTR_ACKNOWLEDGED = "acknowledged"

_OPEN_PATHS = {ACTUATOR_DOOR: "/api/door/open", ACTUATOR_GATE: "/api/gate/open"}


# --- Open provenance stash (read back by the event entity) -----------------


@callback
def stash_open_origin(entry: UrmetConfigEntry, origin: str, context: Context | None = None) -> None:
    """Record who initiated the next open so the event entity can label it."""
    entry.runtime_data.pending_open = PendingOpen(origin, context)


@callback
def take_open(entry: UrmetConfigEntry) -> PendingOpen:
    """Consume the stashed provenance for one gateway ``open`` event."""
    pending = entry.runtime_data.pending_open
    entry.runtime_data.pending_open = None
    return pending if pending is not None else PendingOpen(DEFAULT_ORIGIN, None)


# --- Command coroutines (the single path to the gateway) -------------------


async def async_open(
    entry: UrmetConfigEntry,
    *,
    actuator: str,
    origin: str,
    context: Context | None = None,
) -> bool:
    """Fire an actuator. Return whether the panel acknowledged (DESIGN 6.5).

    One action: the gateway opens inside the live call when one streams and
    places a short call otherwise, so nothing here picks a dialog. ``context``
    carries the user who asked, stashed for the event entity to attribute the
    open to a person in the logbook.
    """
    if actuator not in _OPEN_PATHS:
        raise ServiceValidationError(f"unknown actuator {actuator!r}")
    stash_open_origin(entry, origin, context)
    resp = await _client(entry).async_request("POST", _OPEN_PATHS[actuator])
    return resp.status == 204


async def async_answer(entry: UrmetConfigEntry, *, call_id: str | None) -> None:
    """Answer the named ring, or the only ringing dialog (DESIGN 6.5)."""
    target = call_id or _sole_call(entry, (CallState.RINGING,), "no ringing call to answer")
    _raise_for_status(await _client(entry).async_request("POST", f"/api/call/{target}/answer"))


async def async_hang_up(entry: UrmetConfigEntry, *, call_id: str | None) -> None:
    """Hang up a call. A no-op when nothing is live (DESIGN 6.5, idempotent)."""
    target = call_id or _first_active_call(entry)
    if target is None:
        return
    _raise_for_status(await _client(entry).async_request("DELETE", f"/api/call/{target}"))


async def async_look(entry: UrmetConfigEntry, *, want_video: bool) -> ServiceResponse:
    """Place an on-demand call and return its id (DESIGN 6.5)."""
    resp = await _client(entry).async_request(
        "POST", "/api/call", json={ATTR_WANT_VIDEO: want_video}
    )
    if resp.status != 201:
        _raise_for_status(resp)
    return {ATTR_CALL_ID: str(resp.body.get(ATTR_CALL_ID, ""))}


async def async_set_microphone(entry: UrmetConfigEntry, *, muted: bool) -> None:
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


def _sole_call(entry: UrmetConfigEntry, states: tuple[CallState, ...], msg: str) -> str:
    matches = [c.id for c in _calls(entry) if c.state in states]
    if len(matches) == 1:
        return matches[0]
    raise ServiceValidationError(msg if not matches else f"{msg}: several match")


def _first_active_call(entry: UrmetConfigEntry) -> str | None:
    for call in _calls(entry):
        if call.state.is_active:
            return call.id
    return None


def _raise_for_status(resp: GatewayResponse) -> None:
    if resp.status < 400:
        return
    name = str(resp.body.get("error", "GatewayError"))
    detail = str(resp.body.get("detail", f"gateway returned {resp.status}"))
    raise HomeAssistantError(f"{name}: {detail}")
