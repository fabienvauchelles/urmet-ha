"""WebSocket API and card-registration scenarios (DESIGN 6.6, 7)."""

from __future__ import annotations

from typing import Any

from card_payload import card_offer_payload
from homeassistant.components.websocket_api import const as websocket_api_const
from homeassistant.core import HomeAssistant
from webrtc_gateway import ANSWER_SDP, SESSION_ID, WebrtcGateway
from wp9_support import gateway, setup_entry  # noqa: F401

from custom_components.urmet import CARD_URL

OFFER_SDP = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=urmet-offer\r\n"
WEBSOCKET_COMMANDS = ("urmet/subscribe", "urmet/webrtc/offer", "urmet/webrtc/close")


async def test_subscribe_streams_state_and_events(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    entry = await setup_entry(hass, gateway)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "urmet/subscribe", "entry_id": entry.entry_id})
    result = await client.receive_json()
    assert result["success"] is True

    initial = await client.receive_json()
    assert initial["type"] == "event"
    assert initial["event"]["type"] == "state"
    assert initial["event"]["registered"] is True

    await gateway.push_event(
        {
            "type": "ring",
            "at": None,
            "doorphone": {"mac": gateway.mac, "name": "Portier"},
            "call_id": "c1",
        }
    )
    forwarded = await client.receive_json()
    assert forwarded["type"] == "event"
    assert forwarded["event"]["type"] == "ring"
    assert forwarded["event"]["call_id"] == "c1"


async def test_webrtc_offer_round_trip(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    entry = await setup_entry(hass, gateway)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "urmet/webrtc/offer",
            "entry_id": entry.entry_id,
            "sdp": OFFER_SDP,
            "call_id": "c1",
        }
    )
    result = await client.receive_json()

    assert result["success"] is True
    assert result["result"] == {
        "session_id": SESSION_ID,
        "call_id": "c1",
        "type": "answer",
        "sdp": ANSWER_SDP,
    }
    # The offer reached the gateway with the injected SDP type (DESIGN 6.6).
    assert gateway.last_offer == {"sdp": OFFER_SDP, "type": "offer", "call_id": "c1"}


async def test_webrtc_offer_gateway_failure(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    gateway.offer_status = 503
    entry = await setup_entry(hass, gateway)
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": "urmet/webrtc/offer", "entry_id": entry.entry_id, "sdp": OFFER_SDP}
    )
    result = await client.receive_json()

    assert result["success"] is False
    assert "no route" in result["error"]["message"]


async def test_webrtc_close(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    entry = await setup_entry(hass, gateway)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 7,
            "type": "urmet/webrtc/close",
            "entry_id": entry.entry_id,
            "session_id": SESSION_ID,
        }
    )
    result = await client.receive_json()

    assert result["success"] is True
    assert result["result"] == {}
    assert gateway.closed_sessions == [SESSION_ID]


async def test_unknown_entry_is_reported(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    await setup_entry(hass, gateway)
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 8, "type": "urmet/webrtc/close", "entry_id": "nope", "session_id": SESSION_ID}
    )
    result = await client.receive_json()

    assert result["success"] is False
    assert result["error"]["code"] == "not_found"


async def test_card_static_path_registered(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_client: Any,
) -> None:
    await setup_entry(hass, gateway)

    # The static path is served over HA's own HTTP, so the frontend loads it as a
    # module (add_extra_js_url is exercised on a full instance; here we assert the
    # route the card is served from, DESIGN 6.2).
    http_client = await hass_client()
    response = await http_client.get(CARD_URL)
    assert response.status == 200
    body = await response.text()
    assert "urmet-portier-card" in body


async def test_setup_registers_websocket_commands(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
) -> None:
    """Setting up the entry registers the three card commands (DESIGN 6.6)."""
    await setup_entry(hass, gateway)

    handlers = hass.data.get(websocket_api_const.DOMAIN, {})
    for command in WEBSOCKET_COMMANDS:
        assert command in handlers, f"{command} was not registered"


async def test_card_offer_payload_matches_websocket_schema(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    """The exact keys the card sends to urmet/webrtc/offer are accepted here.

    The payload is read from the card source (``card/src/link/hass.ts``), never
    hand-written, and sent at the real ``websocket_api`` schema. That schema
    forbids unexpected keys, so a stray key (the ``sdp_type`` regression) or a
    renamed one fails this test instead of only failing at runtime on hardware.
    """
    entry = await setup_entry(hass, gateway)
    client = await hass_ws_client(hass)

    keys, resolved = card_offer_payload()
    assert "sdp_type" not in keys, "the card must not send sdp_type (DESIGN 5.2, 6.6)"

    values: dict[str, Any] = {
        "type": resolved["type"],
        "entry_id": entry.entry_id,
        "sdp": OFFER_SDP,
        "call_id": "c1",
    }
    # Build the frame from the card's own keys. An unexpected key would carry a
    # placeholder value and the schema would reject the whole message.
    message: dict[str, Any] = {"id": 11}
    for key in keys:
        message[key] = values.get(key, "unexpected")

    await client.send_json(message)
    result = await client.receive_json()

    assert result["success"] is True, result
    assert result["result"]["session_id"] == SESSION_ID
    # The handler injects type "offer" and forwards only sdp and call_id (DESIGN 5.2).
    assert gateway.last_offer == {"sdp": OFFER_SDP, "type": "offer", "call_id": "c1"}
