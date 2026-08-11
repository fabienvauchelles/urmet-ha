"""Every event type on the WebSocket (DESIGN 5.3), and the rule that binds them.

A subscriber gets a ``state`` event the moment it connects, and a ``state`` event
follows every other event, so ``sessions`` and the event can never disagree. Each
scenario connects at a point where nothing else is publishing, drives one action,
and reads the event it caused immediately followed by its state.
"""

from __future__ import annotations

from .http_support import DOORPHONE_MAC, http_harness


async def test_state_first_on_connect_and_again_on_reconnect() -> None:
    async with http_harness() as h:
        await h.wait_registered()
        async with h.events() as stream:
            snapshot = await stream.expect("state")
            assert snapshot["registered"] is True
            assert snapshot["doorphone"] == {"mac": DOORPHONE_MAC, "name": "Front Gate"}
        # A second subscriber is given the whole state too, not just what it missed.
        async with h.events() as again:
            assert (await again.expect("state"))["registered"] is True


async def test_ring_and_call_events_each_followed_by_state() -> None:
    async with http_harness() as h:
        await h.wait_registered()
        async with h.events() as stream:
            await stream.expect("state")
            call_id = await h.ring()

            assert (await stream.expect("ring"))["call_id"] == call_id
            await stream.expect("state")
            call = await stream.expect("call")
            assert call["state"] == "ringing"
            assert call["direction"] == "incoming"
            await stream.expect("state")


async def test_open_event_followed_by_state() -> None:
    async with http_harness() as h:
        await h.wait_registered()
        call_id = await h.place_call()
        async with h.events() as stream:
            await stream.expect("state")

            opened = await h.post("/api/door/open", json={"call_id": call_id})
            assert opened.status == 204

            event = await stream.expect("open")
            assert event["actuator"] == "door"
            assert event["acknowledged"] is True
            await stream.expect("state")


async def test_registration_event_carries_the_registrar_code() -> None:
    async with http_harness(gate_start=True) as h, h.events() as stream:
        assert (await stream.expect("state"))["registered"] is False
        h.release_start()
        registration = await stream.until("registration", registered=True)
        assert registration["status_code"] == 200
        assert (await stream.until("state"))["registered"] is True


async def test_webrtc_event_followed_by_state() -> None:
    async with http_harness(with_media=True) as h:
        await h.wait_registered()
        call_id = await h.place_call()
        async with h.events() as stream:
            await stream.expect("state")

            offered = await h.post(
                "/api/webrtc/offer", json={"sdp": "v=0", "type": "offer", "call_id": call_id}
            )
            assert offered.status == 201

            event = await stream.expect("webrtc")
            assert event["call_id"] == call_id
            assert event["session_id"] == "1"
            await stream.expect("state")
