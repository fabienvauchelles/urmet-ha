"""The WP1 use-case graph a scenario drives, built on the shared harness.

The composition here mirrors the production one: a single worker thread, a
registration supervisor that owns the binding and rebuilds the client on loss, a
callback bridge that marshals every SIP callback onto the loop, and a command
port that resolves the current client through the holder the supervisor updates.
``open_graph`` raises a registered service over a shared cold harness and tears it
down again, so a scenario reads as one ``async with`` block.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any

from urmet_sdk import Actuator, CallHandle, Doorphone, UrmetClient

from urmet_gateway.domain.models import SessionState, SessionView
from urmet_gateway.domain.ports import MediaChanged, SessionClosed
from urmet_gateway.runtime import GatewayRuntime
from urmet_gateway.sip import (
    CallbackBridge,
    ClientHolder,
    RegistrationSupervisor,
    SdkWorker,
    rebuilding_factory,
    registration_publisher,
)
from urmet_gateway.usecases import DoorphoneService, EventBus, Subscription

from .harness import DOORPHONE_MAC, GATE_TIMEOUT_S, Harness, build_harness

__all__ = ["DOORPHONE_MAC", "Harness", "SdkDoorphonePort", "ServiceGraph", "open_graph"]

ClientProvider = Callable[[], UrmetClient]


class SdkDoorphonePort:
    """A command ``DoorphonePort`` over whatever client the holder points at.

    It owns no client and no lifecycle: the supervisor builds and registers, and
    this port only runs commands, each on the one shared worker thread, against
    the client resolved at command time. A rebuild is therefore invisible to it.
    """

    def __init__(self, *, provider: ClientProvider, worker: SdkWorker) -> None:
        self._provider = provider
        self._worker = worker

    @property
    def registered(self) -> bool:
        return self._provider().registered

    def known_doorphone(self) -> Doorphone | None:
        return self._provider().known_doorphone()

    async def view_door(self, *, want_video: bool) -> CallHandle:
        return await self._worker.run(self._provider().view_door, want_video=want_video)

    async def answer(self, call: CallHandle) -> None:
        await self._worker.run(self._provider().answer, call)

    async def hangup(self, call: CallHandle) -> None:
        await self._worker.run(self._provider().hangup, call)

    async def open_during(self, call: CallHandle, actuator: Actuator) -> None:
        await self._worker.run(self._provider().open_during, call, actuator)

    async def open_on_demand(self, actuator: Actuator) -> None:
        client = self._provider()
        command = client.open_door if actuator is Actuator.DOOR else client.open_gate
        await self._worker.run(command)

    async def set_mic_muted(self, muted: bool) -> None:
        await self._worker.run(self._provider().set_mic_muted, muted)


class FakeSession:
    """A ``MediaSessionPort`` with no aiortc: its ``aclose`` stands in for the tap
    release, so a scenario proving no tap is left on a dead dialog asserts it ran."""

    def __init__(self, session_id: str, call: CallHandle, on_closed: SessionClosed) -> None:
        self._id = session_id
        self._call_id = call.id
        self._on_closed = on_closed
        self._closed = False
        self.answered: list[str] = []
        self.close_reasons: list[str] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def call_id(self) -> str:
        return self._call_id

    async def answer(self, sdp: str) -> str:
        self.answered.append(sdp)
        return f"answer-to:{sdp}"

    async def aclose(self, *, reason: str) -> None:
        self.close_reasons.append(reason)
        if self._closed:
            return
        self._closed = True
        self._on_closed(self, reason)

    def view(self) -> SessionView:
        state = SessionState.CLOSED if self._closed else SessionState.OPEN
        return SessionView(
            session_id=self._id, call_id=self._call_id, state=state, connection="connected"
        )


class FakeSessionFactory:
    """Builds ``FakeSession`` objects and remembers every one it made."""

    def __init__(self) -> None:
        self.created: list[FakeSession] = []

    def create(
        self,
        *,
        session_id: str,
        call: CallHandle,
        on_closed: SessionClosed,
        on_media_change: MediaChanged,
    ) -> FakeSession:
        session = FakeSession(session_id, call, on_closed)
        self.created.append(session)
        return session


class Recorder:
    """Collects every event the bus publishes, in order, on a background task."""

    def __init__(self, subscription: Subscription) -> None:
        self._sub = subscription
        self.events: list[Any] = []

    async def run(self) -> None:
        async for event in self._sub:
            self.events.append(event)

    def typed(self, event_type: str) -> list[Any]:
        return [e for e in self.events if getattr(e, "type", None) == event_type]


class ServiceGraph:
    """A started ``DoorphoneService`` and the levers a scenario drives it with."""

    def __init__(
        self,
        *,
        harness: Harness,
        port: SdkDoorphonePort,
        bus: EventBus,
        service: DoorphoneService,
        factory: FakeSessionFactory | None,
        recorder: Recorder,
        task: asyncio.Task[None],
        runtime: GatewayRuntime,
    ) -> None:
        self.harness = harness
        self.transport = harness.transport
        self.doorphone = harness.doorphone
        self.port = port
        self.bus = bus
        self.service = service
        self.factory = factory
        self.recorder = recorder
        self._task = task
        self._runtime = runtime

    async def settle(self) -> None:
        for _ in range(5):
            await asyncio.sleep(0)

    async def drain(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.transport.drain)
        await self.settle()

    async def ring(self, *, named: bool = True) -> str:
        loop = asyncio.get_running_loop()
        press = functools.partial(self.transport.simulate_ring, self.doorphone, named=named)
        call: CallHandle = await loop.run_in_executor(None, press)
        await self.settle()
        return call.id

    async def reach_invite(self) -> CallHandle:
        loop = asyncio.get_running_loop()
        reached = await loop.run_in_executor(None, self.transport.inviting.wait, GATE_TIMEOUT_S)
        assert reached, "no INVITE ever reached the transport"
        call = self.transport.invited
        assert call is not None
        return call

    async def end_call(self, call: CallHandle) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, functools.partial(self.transport.end_call, call))
        await self.settle()

    def events(self) -> list[Any]:
        return self.recorder.events

    def typed(self, event_type: str) -> list[Any]:
        return self.recorder.typed(event_type)

    async def aclose(self) -> None:
        await self._runtime.shutdown()
        await self.settle()
        with suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(self._task, GATE_TIMEOUT_S)


@asynccontextmanager
async def open_graph(
    *,
    open_acknowledged: bool = True,
    video_ready: bool = True,
    with_media: bool = False,
) -> AsyncIterator[ServiceGraph]:
    """Build a cold harness, raise a registered service over it, and tear both down.

    Self-contained on purpose: it owns the harness so a scenario needs no shared
    fixture, which keeps the use-case tests standing whatever else shares this
    directory's conftest. The supervisor registers in the background, so the
    scenario is only handed a warm, quiescent graph once the binding is up and its
    boot events have drained, before the recorder subscribes.
    """
    harness = build_harness(open_acknowledged=open_acknowledged, video_ready=video_ready)
    loop = asyncio.get_running_loop()
    worker = SdkWorker()
    holder: ClientHolder[UrmetClient] = ClientHolder()
    bus = EventBus()
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
    await runtime.start()
    await _reach_registered(port, harness.transport)
    recorder = Recorder(bus.subscribe())
    task = asyncio.create_task(recorder.run())
    graph = ServiceGraph(
        harness=harness,
        port=port,
        bus=bus,
        service=service,
        factory=factory,
        recorder=recorder,
        task=task,
        runtime=runtime,
    )
    await graph.settle()
    try:
        yield graph
    finally:
        await graph.aclose()
        harness.transport.shutdown()


async def _reach_registered(port: SdkDoorphonePort, transport: Any) -> None:
    """Wait for the boot REGISTER, then drain the callbacks it left in flight."""
    loop = asyncio.get_running_loop()
    for _ in range(200):
        if port.registered:
            await loop.run_in_executor(None, transport.drain)
            for _ in range(5):
                await asyncio.sleep(0)
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the service never registered")
