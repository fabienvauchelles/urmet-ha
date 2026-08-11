"""A gateway double speaking the WP9 surface of the contract (DESIGN 5.2, 5.3).

Beyond the health/state/events routes the config-flow double serves, this one
adds ``GET /api/diagnostics``, ``POST /api/webrtc/offer`` and
``DELETE /api/webrtc/session/{id}``, and can push arbitrary events into the
WebSocket so the repairs monitor and the card subscription can be exercised.

Kept separate from ``gateway_double`` so WP9 owns its own fixture surface.
"""

from __future__ import annotations

import socket
from typing import Any

from aiohttp import web
from homeassistant.util import dt as dt_util

DOORPHONE_MAC = "00:11:22:33:44:55"
ANSWER_SDP = "v=0\r\no=- 2 2 IN IP4 127.0.0.1\r\ns=urmet-answer\r\n"
SESSION_ID = "session-1"

# A deterministic gateway diagnostics body for the golden-file test (DESIGN 6.7).
DIAGNOSTICS_BODY: dict[str, Any] = {
    "registered": True,
    "last_invite_status": 200,
    "director_failures": {"count": 0},
    "calls_total": 3,
    "opens": {"door": 2, "gate": 1},
}


def free_tcp_port() -> int:
    """Reserve and release a loopback TCP port, returning its number."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class WebrtcGateway:
    """The WP9 slice of the gateway contract, backed by aiohttp."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.registered = True
        self.mac = DOORPHONE_MAC
        self.name = "Portier"
        self.has_doorphone = True
        self.offer_status = 201
        self.diagnostics_body = dict(DIAGNOSTICS_BODY)
        self.last_offer: dict[str, Any] | None = None
        self.closed_sessions: list[str] = []
        self._runner: web.AppRunner | None = None
        self._sockets: set[web.WebSocketResponse] = set()

    @property
    def host(self) -> str:
        return "127.0.0.1"

    def state_dict(self) -> dict[str, Any]:
        doorphone = {"mac": self.mac, "name": self.name} if self.has_doorphone else None
        return {
            "registered": self.registered,
            "doorphone": doorphone,
            "calls": [],
            "mic_muted": True,
            "sessions": [],
        }

    def _state_event(self) -> dict[str, Any]:
        return {"type": "state", "at": dt_util.utcnow().isoformat(), **self.state_dict()}

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/api/health", self._handle_health)
        app.router.add_get("/api/state", self._handle_state)
        app.router.add_get("/api/diagnostics", self._handle_diagnostics)
        app.router.add_get("/api/events", self._handle_events)
        app.router.add_post("/api/webrtc/offer", self._handle_offer)
        app.router.add_delete("/api/webrtc/session/{session_id}", self._handle_close)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port, reuse_address=True)
        await site.start()

    async def stop(self) -> None:
        for ws in list(self._sockets):
            await ws.close()
        self._sockets.clear()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def push_event(self, payload: dict[str, Any]) -> None:
        """Send one event frame to every subscriber (DESIGN 5.3)."""
        for ws in list(self._sockets):
            await ws.send_json(payload)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _handle_state(self, request: web.Request) -> web.Response:
        return web.json_response(self.state_dict())

    async def _handle_diagnostics(self, request: web.Request) -> web.Response:
        return web.json_response(self.diagnostics_body)

    async def _handle_offer(self, request: web.Request) -> web.Response:
        self.last_offer = await request.json()
        if self.offer_status != 201:
            return web.json_response(
                {"error": "MediaUnavailableError", "detail": "no route for the invite"},
                status=self.offer_status,
            )
        return web.json_response(
            {
                "session_id": SESSION_ID,
                "call_id": self.last_offer.get("call_id") or "call-1",
                "type": "answer",
                "sdp": ANSWER_SDP,
            },
            status=201,
        )

    async def _handle_close(self, request: web.Request) -> web.Response:
        self.closed_sessions.append(request.match_info["session_id"])
        return web.Response(status=204)

    async def _handle_events(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30.0)
        await ws.prepare(request)
        self._sockets.add(ws)
        await ws.send_json(self._state_event())
        try:
            async for _msg in ws:
                pass  # nothing a client sends is a command (DESIGN 5.3)
        finally:
            self._sockets.discard(ws)
        return ws
