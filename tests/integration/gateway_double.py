"""An aiohttp double for the urmet-gateway add-on (DESIGN 5.2, 5.3).

It serves the three routes the integration reads (``/api/health``,
``/api/state``, ``/api/events``) on a loopback port, and a WebSocket that emits a
``state`` event on connect. Tests change its answer, drop its sockets and stop
and restart it on the same port, which is what a gateway restart looks like to
the integration.
"""

from __future__ import annotations

import socket
from typing import Any

from aiohttp import web
from homeassistant.util import dt as dt_util

DOORPHONE_MAC = "00:11:22:33:44:55"
OTHER_MAC = "aa:bb:cc:dd:ee:ff"


def free_tcp_port() -> int:
    """Reserve and release a loopback TCP port, returning its number."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class FakeGateway:
    """The gateway contract of DESIGN 5.2 and 5.3, backed by aiohttp."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.registered = True
        self.mac = DOORPHONE_MAC
        self.name = "Portier"
        self.has_doorphone = True
        self.mic_muted = True
        self.calls: list[dict[str, Any]] = []
        self.open_status = 204
        self.next_call_id = "call-1"
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
            "calls": list(self.calls),
            "mic_muted": self.mic_muted,
            "sessions": [],
        }

    def _state_event(self) -> dict[str, Any]:
        return {"type": "state", "at": dt_util.utcnow().isoformat(), **self.state_dict()}

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/api/health", self._handle_health)
        app.router.add_get("/api/state", self._handle_state)
        app.router.add_get("/api/events", self._handle_events)
        app.router.add_post("/api/door/open", self._handle_open)
        app.router.add_post("/api/gate/open", self._handle_open)
        app.router.add_post("/api/mic", self._handle_mic)
        app.router.add_post("/api/call", self._handle_place_call)
        app.router.add_post("/api/call/{call_id}/answer", self._handle_answer)
        app.router.add_delete("/api/call/{call_id}", self._handle_delete_call)
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

    async def push_state(self) -> None:
        payload = self._state_event()
        for ws in list(self._sockets):
            await ws.send_json(payload)

    async def push_open(
        self, actuator: str, acknowledged: bool, call_id: str | None = None
    ) -> None:
        payload = {
            "type": "open",
            "at": dt_util.utcnow().isoformat(),
            "actuator": actuator,
            "acknowledged": acknowledged,
            "call_id": call_id,
        }
        for ws in list(self._sockets):
            await ws.send_json(payload)

    async def push_ring(self, call_id: str | None = None) -> None:
        payload = {
            "type": "ring",
            "at": dt_util.utcnow().isoformat(),
            "doorphone": {"mac": self.mac, "name": self.name},
            "call_id": call_id,
        }
        for ws in list(self._sockets):
            await ws.send_json(payload)

    async def _handle_open(self, request: web.Request) -> web.Response:
        actuator = "door" if request.path.endswith("/door/open") else "gate"
        if self.open_status == 204:
            await self.push_open(actuator, True)
            return web.Response(status=204)
        return web.json_response(
            {
                "error": "OpenNotAcknowledgedError",
                "detail": "the actuator INFO went unanswered; the door state is unknown",
            },
            status=self.open_status,
        )

    async def _handle_mic(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.mic_muted = bool(body.get("muted", True))
        await self.push_state()
        return web.Response(status=204)

    async def _handle_place_call(self, request: web.Request) -> web.Response:
        return web.json_response({"call_id": self.next_call_id}, status=201)

    async def _handle_answer(self, request: web.Request) -> web.Response:
        return web.Response(status=204)

    async def _handle_delete_call(self, request: web.Request) -> web.Response:
        return web.Response(status=204)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _handle_state(self, request: web.Request) -> web.Response:
        return web.json_response(self.state_dict())

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
