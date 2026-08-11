"""WebSocket API the Portier card talks to (DESIGN 6.6, 7).

Three commands the card sends over Home Assistant's own WebSocket, so signalling
shares the frontend origin and HA authentication (DESIGN 2.3): ``urmet/subscribe``
streams the gateway state and every event to the card, and ``urmet/webrtc/offer``
and ``urmet/webrtc/close`` proxy the SDP round trip to the gateway.

The SDP ``type`` field of DESIGN 6.6 is not carried on the wire: the WebSocket
envelope already owns ``type`` for the command name, so the offer command injects
``"offer"`` when proxying and the answer's own ``type`` comes back inside the reply.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .client import GatewayConnectionError
from .const import DOMAIN
from .coordinator import UrmetConfigEntry
from .events import GatewayEvent, StateEvent, UnknownEvent
from .models import StateView
from .repairs import note_offer_status

WEBRTC_OFFER_PATH = "/api/webrtc/offer"
WEBRTC_SESSION_PATH = "/api/webrtc/session/{session_id}"


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the three card commands once per Home Assistant instance."""
    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_webrtc_offer)
    websocket_api.async_register_command(hass, websocket_webrtc_close)


@callback
def _resolve_entry(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> UrmetConfigEntry | None:
    """Return the loaded Urmet entry named by ``entry_id``, or send an error."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"no loaded urmet config entry {msg['entry_id']}",
        )
        return None
    return entry


def _event_payload(event: GatewayEvent) -> dict[str, Any]:
    """Rebuild the gateway wire frame from a typed event (DESIGN 5.3)."""
    if isinstance(event, UnknownEvent):
        return dict(event.raw)
    payload = asdict(event)
    if isinstance(event, StateEvent):
        payload.update(payload.pop("state"))
    at = payload.get("at")
    if isinstance(at, datetime):
        payload["at"] = at.isoformat()
    return payload


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "urmet/subscribe",
        vol.Required("entry_id"): str,
    }
)
def websocket_subscribe(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Stream the initial state then every gateway event to the card."""
    entry = _resolve_entry(hass, connection, msg)
    if entry is None:
        return
    data = entry.runtime_data

    @callback
    def _forward(event: GatewayEvent) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], _event_payload(event)))

    # Subscribe before reading the snapshot so nothing is lost between the two.
    connection.subscriptions[msg["id"]] = data.client.add_event_listener(_forward)
    connection.send_result(msg["id"])
    state: StateView | None = data.coordinator.data
    if state is not None:
        initial = StateEvent(at=dt_util.utcnow(), state=state)
        connection.send_message(websocket_api.event_message(msg["id"], _event_payload(initial)))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "urmet/webrtc/offer",
        vol.Required("entry_id"): str,
        vol.Required("sdp"): str,
        vol.Optional("call_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def websocket_webrtc_offer(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Proxy the SDP offer to the gateway and return its answer (DESIGN 5.2)."""
    entry = _resolve_entry(hass, connection, msg)
    if entry is None:
        return
    body = {"sdp": msg["sdp"], "type": "offer", "call_id": msg.get("call_id")}
    try:
        response = await entry.runtime_data.client.async_request(
            "POST", WEBRTC_OFFER_PATH, json=body
        )
    except GatewayConnectionError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return
    note_offer_status(entry, response.status)
    if response.status != 201:
        connection.send_error(
            msg["id"], websocket_api.ERR_UNKNOWN_ERROR, _detail(response.body, response.status)
        )
        return
    connection.send_result(msg["id"], response.body)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "urmet/webrtc/close",
        vol.Required("entry_id"): str,
        vol.Required("session_id"): str,
    }
)
@websocket_api.async_response
async def websocket_webrtc_close(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Close a media session on the gateway (idempotent, DESIGN 5.2)."""
    entry = _resolve_entry(hass, connection, msg)
    if entry is None:
        return
    path = WEBRTC_SESSION_PATH.format(session_id=msg["session_id"])
    try:
        await entry.runtime_data.client.async_request("DELETE", path)
    except GatewayConnectionError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return
    connection.send_result(msg["id"], {})


def _detail(body: dict[str, Any], status: int) -> str:
    """The gateway's failure detail, or a plain status fallback (DESIGN 5.2)."""
    detail = body.get("detail") or body.get("error")
    return str(detail) if detail else f"gateway returned {status}"
