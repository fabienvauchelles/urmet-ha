"""Every route in the HTTP contract (DESIGN 5.2), driven over the real chain.

One scenario per group of routes, each asserting the status, the body shape and
the failures the contract pins: an unacknowledged open is 502 and says the state
is unknown, an unknown call answered is 404 but deleted is 204, an offer with no
tap is 503 and one with no streaming call is 409, and an off-shape body is a 400
that names the field.
"""

from __future__ import annotations

from .http_support import DOORPHONE_MAC, http_harness


async def test_health_state_diagnostics() -> None:
    async with http_harness() as h:
        await h.wait_registered()

        health = await h.get("/api/health")
        assert health.status == 200
        assert await health.json() == {"ok": True}

        state = await h.get("/api/state")
        assert state.status == 200
        body = await state.json()
        assert body == {
            "registered": True,
            "doorphone": {"mac": DOORPHONE_MAC, "name": "Front Gate"},
            "calls": [],
            "mic_muted": True,
            "sessions": [],
        }

        diag = await h.get("/api/diagnostics")
        assert diag.status == 200
        dump = await diag.json()
        assert dump["state"]["registered"] is True
        assert dump["settings"]["doorphone_mac"] == DOORPHONE_MAC
        assert dump["director_failures"] == {"count": 0}


async def test_call_answer_open_hangup() -> None:
    async with http_harness() as h:
        await h.wait_registered()

        call_id = await h.ring()
        answered = await h.post(f"/api/call/{call_id}/answer")
        assert answered.status == 204
        assert h.transport.answered == [call_id]

        opened = await h.post("/api/door/open", json={"call_id": call_id})
        assert opened.status == 204
        assert len(h.transport.opens) == 1

        # The gate too, on its own placed call, with an empty body for the default.
        gate = await h.post("/api/gate/open")
        assert gate.status == 204

        hung = await h.delete(f"/api/call/{call_id}")
        assert hung.status == 204
        # Idempotent: a call already gone is already hung up, so 204 not 404.
        again = await h.delete(f"/api/call/{call_id}")
        assert again.status == 204


async def test_place_call_and_mic() -> None:
    async with http_harness() as h:
        await h.wait_registered()

        created = await h.post("/api/call", json={"want_video": True})
        assert created.status == 201
        call_id = (await created.json())["call_id"]
        assert call_id

        # An empty body asks for the default, and the service starts muted.
        unmuted = await h.post("/api/mic", json={"muted": False})
        assert unmuted.status == 204
        assert h.transport.mic_muted() is False
        assert (await (await h.get("/api/state")).json())["mic_muted"] is False


async def test_offer_and_session() -> None:
    async with http_harness(with_media=True) as h:
        await h.wait_registered()
        call_id = await h.place_call()

        offered = await h.post(
            "/api/webrtc/offer", json={"sdp": "v=0-browser", "type": "offer", "call_id": call_id}
        )
        assert offered.status == 201
        answer = await offered.json()
        assert answer == {
            "session_id": "1",
            "call_id": call_id,
            "type": "answer",
            "sdp": "answer-to:v=0-browser",
        }

        closed = await h.delete(f"/api/webrtc/session/{answer['session_id']}")
        assert closed.status == 204
        # Idempotent, exactly as a call ending closes its own session.
        assert (await h.delete("/api/webrtc/session/999")).status == 204


async def test_answer_unknown_call_is_404() -> None:
    async with http_harness() as h:
        await h.wait_registered()
        response = await h.post("/api/call/nope/answer")
        assert response.status == 404
        assert (await response.json())["error"] == "UnknownCallError"


async def test_open_unacknowledged_is_502_and_unknown() -> None:
    async with http_harness(open_acknowledged=False) as h:
        await h.wait_registered()
        response = await h.post("/api/door/open")
        assert response.status == 502
        body = await response.json()
        assert body["error"] == "OpenNotAcknowledgedError"
        assert "the door state is unknown" in body["detail"]


async def test_offer_without_tap_is_503() -> None:
    async with http_harness(with_media=False) as h:
        await h.wait_registered()
        response = await h.post("/api/webrtc/offer", json={"sdp": "v=0", "type": "offer"})
        assert response.status == 503
        assert (await response.json())["error"] == "MediaUnavailableError"


async def test_offer_without_streaming_call_is_409() -> None:
    async with http_harness(with_media=True) as h:
        await h.wait_registered()
        response = await h.post("/api/webrtc/offer", json={"sdp": "v=0", "type": "offer"})
        assert response.status == 409
        assert (await response.json())["error"] == "NoStreamingCallError"


async def test_off_shape_body_is_400_naming_the_field() -> None:
    async with http_harness() as h:
        await h.wait_registered()

        missing = await h.post("/api/mic", json={})
        assert missing.status == 400
        assert "muted" in (await missing.json())["detail"]

        wrong_type = await h.post("/api/mic", json={"muted": "loud"})
        assert wrong_type.status == 400
        assert "muted" in (await wrong_type.json())["detail"]

        extra = await h.post("/api/call", json={"nope": 1})
        assert extra.status == 400
        assert "nope" in (await extra.json())["detail"]


async def test_diagnostics_page_served_through_ingress() -> None:
    async with http_harness(serve_diag=True) as h:
        page = await h.get("/")
        assert page.status == 200
        assert "Urmet gateway" in await page.text()
        script = await h.get("/diag.js")
        assert script.status == 200
        assert "api/events" in await script.text()
