"""The HTTP application under test, wired over the SDK's published doubles.

What is real is everything the gateway and the SDK own: ``UrmetClient``, the
``DoorphoneService``, the aiohttp application and its lifecycle. What is faked is
the two boundaries the SDK injects (the cloud plane and the SIP transport) plus a
media tap, and the WebRTC session, which a deterministic test does not build over
aiortc. So a scenario that passes here says the real HTTP chain works.

The server listens on a hand-built loopback socket, so a test can pin its send
buffer and make backpressure a number this file chose rather than the kernel's.
The boot can be gated, so a test observes the port answering before the SDK is up.
"""

from __future__ import annotations

import asyncio
import functools
import socket
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web
from urmet_sdk import CallHandle, UrmetClient

import urmet_gateway
from urmet_gateway.http import create_app
from urmet_gateway.runtime import GatewayRuntime
from urmet_gateway.sip import (
    CallbackBridge,
    ClientHolder,
    RegistrationSupervisor,
    SdkWorker,
    rebuilding_factory,
    registration_publisher,
)
from urmet_gateway.usecases import DoorphoneService, EventBus

from .event_stream import EventStream, Follower
from .harness import DOORPHONE_MAC, DOORPHONE_NAME, build_harness
from .service_graph import FakeSessionFactory, SdkDoorphonePort

__all__ = [
    "DOORPHONE_MAC",
    "DOORPHONE_NAME",
    "EventStream",
    "Follower",
    "HttpHarness",
    "http_harness",
]

DIAG_DIR = Path(urmet_gateway.__path__[0]) / "diag"
RECEIVE_TIMEOUT_S = 10.0
MAX_SKIPPED = 400


class HttpHarness:
    """The application under test, and the levers a scenario drives it with."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        base: str,
        runner: web.AppRunner,
        harness: Any,
        bus: EventBus,
        service: DoorphoneService,
        factory: FakeSessionFactory | None,
        gate: threading.Event | None,
    ) -> None:
        self._session = session
        self._base = base
        self._runner = runner
        self.harness = harness
        self.transport = harness.transport
        self.doorphone = harness.doorphone
        self.bus = bus
        self.service = service
        self.factory = factory
        self._gate = gate

    async def get(self, path: str) -> aiohttp.ClientResponse:
        return await self._session.get(self._base + path)

    async def post(self, path: str, json: Any = None) -> aiohttp.ClientResponse:
        return await self._session.post(self._base + path, json=json)

    async def delete(self, path: str) -> aiohttp.ClientResponse:
        return await self._session.delete(self._base + path)

    @asynccontextmanager
    async def events(self) -> AsyncIterator[EventStream]:
        """One subscriber on ``GET /api/events``, closed when the block ends."""
        async with self._session.ws_connect(self._base + "/api/events") as ws:
            yield EventStream(ws)

    def release_start(self) -> None:
        """Let a gated boot proceed past the held ``start``."""
        assert self._gate is not None, "this harness was built without a start gate"
        self._gate.set()

    async def wait_registered(self) -> None:
        """Poll the state until the binding exists, so a scenario reads a warm gateway.

        The state snapshot flips ``registered`` the moment the SDK property does, but
        the registration's own ``registration`` and trailing ``state`` bus events are
        published on the loop through ``call_soon_threadsafe`` and can land later. A
        drain here flushes those before the caller subscribes, so a warm gateway is
        also a quiescent one and no boot event is left in flight.
        """
        for _ in range(200):
            response = await self.get("/api/state")
            if (await response.json())["registered"]:
                await self.drain()
                return
            await asyncio.sleep(0.01)
        raise AssertionError("the gateway never registered")

    async def drain(self) -> None:
        """Wait for every callback the double still owes, then let the loop take them."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.transport.drain)
        for _ in range(5):
            await asyncio.sleep(0)

    async def ring(self, *, named: bool = True) -> str:
        """Press the doorbell and answer the call id the panel offered."""
        loop = asyncio.get_running_loop()
        press = functools.partial(self.transport.simulate_ring, self.doorphone, named=named)
        call: CallHandle = await loop.run_in_executor(None, press)
        await self.drain()
        return call.id

    async def place_call(self, *, want_video: bool = True) -> str:
        """Place a call through the API, and read back the id it streamed on."""
        response = await self.post("/api/call", json={"want_video": want_video})
        assert response.status == 201, await response.text()
        await self.drain()
        return str((await response.json())["call_id"])

    async def close(self) -> None:
        """Release whatever is held, then shut the application and the doubles down.

        The gate is set first so a boot frozen at REGISTER can complete on the
        worker thread; the runner cleanup then runs the ordered shutdown, which
        releases the binding and joins that thread.
        """
        if self._gate is not None:
            self._gate.set()
        await self._session.close()
        await self._runner.cleanup()
        self.transport.shutdown()


@asynccontextmanager
async def http_harness(
    *,
    registration: str = "accept",
    open_acknowledged: bool = True,
    video_ready: bool = True,
    with_media: bool = False,
    bus_capacity: int = 64,
    gate_start: bool = False,
    send_buffer: int | None = None,
    serve_diag: bool = False,
) -> AsyncIterator[HttpHarness]:
    """Wire the application over the doubles, serve it, and tear everything down."""
    gate = threading.Event() if gate_start else None
    harness = build_harness(
        registration=registration,
        open_acknowledged=open_acknowledged,
        video_ready=video_ready,
        login_gate=gate,
    )
    loop = asyncio.get_running_loop()
    worker = SdkWorker()
    holder: ClientHolder[UrmetClient] = ClientHolder()
    bus = EventBus(capacity=bus_capacity)
    port = SdkDoorphonePort(provider=holder.current, worker=worker)
    factory = FakeSessionFactory() if with_media else None
    service = DoorphoneService(port=port, bus=bus, clock=harness.clock, factory=factory)
    bridge = CallbackBridge(
        loop=loop, on_ring=service.ring_arrived, on_call=service.call_state_arrived
    )

    def build_client() -> UrmetClient:
        client = harness.build_client()
        bridge.bind(client)
        holder.set(client)
        return client

    supervisor = RegistrationSupervisor(
        build_client=rebuilding_factory(build_client),
        worker=worker,
        publish=registration_publisher(bus=bus, service=service, clock=harness.clock),
        is_busy=lambda: worker.busy,
        on_connected=service.realign,
    )
    runtime = GatewayRuntime(bus=bus, worker=worker, supervisor=supervisor, service=service)
    app = create_app(
        service=service,
        bus=bus,
        clock=harness.clock,
        settings_echo=lambda: {"doorphone_mac": DOORPHONE_MAC, "null_sound_device": True},
        failures=lambda: 0,
        diag_dir=DIAG_DIR if serve_diag else None,
        on_startup=runtime.start,
        on_cleanup=runtime.shutdown,
    )
    sock, base = _listening_socket(send_buffer)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.SockSite(runner, sock).start()
    session = aiohttp.ClientSession()
    http = HttpHarness(
        session=session,
        base=base,
        runner=runner,
        harness=harness,
        bus=bus,
        service=service,
        factory=factory,
        gate=gate,
    )
    try:
        yield http
    finally:
        await http.close()


def _listening_socket(send_buffer: int | None) -> tuple[socket.socket, str]:
    """A bound loopback socket, its send buffer pinned when a test asks for it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if send_buffer is not None:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, send_buffer)
    sock.bind(("127.0.0.1", 0))
    sock.listen(64)
    return sock, f"http://127.0.0.1:{sock.getsockname()[1]}"
