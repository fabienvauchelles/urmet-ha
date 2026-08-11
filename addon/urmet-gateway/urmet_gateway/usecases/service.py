"""The facade the HTTP layer calls: the SDK driven from asyncio.

It owns the calls, the media and the event stream, and nothing else owns any of
them. It does not own registration: the supervisor holds the binding's lifecycle
and hands this layer a client that can change under it on a reconnect, reached
through the ``DoorphonePort``. Into the SDK, every blocking call goes through that
port, already made awaitable. Out of the SDK, the ring and call-state callbacks
are handed here already marshalled onto the loop by the bridge, so this layer
never touches a worker thread and never calls ``call_soon_threadsafe`` itself.
Every non-state event it publishes is followed by a ``state`` event, so a
subscriber's view can never disagree with what it saw.
"""

from __future__ import annotations

from urmet_sdk import CallHandle, CallState
from urmet_sdk import RingEvent as SdkRingEvent

from urmet_gateway.domain.errors import OpenNotAcknowledgedError
from urmet_gateway.domain.models import (
    ActuatorName,
    CallEvent,
    Direction,
    DoorphoneView,
    Event,
    OpenEvent,
    RingEvent,
    SessionAnswer,
    StateEvent,
    StateView,
)
from urmet_gateway.domain.ports import Clock, DoorphonePort, SessionFactory
from urmet_gateway.usecases.calls import TERMINAL_STATES, CallBook
from urmet_gateway.usecases.events import EventBus
from urmet_gateway.usecases.sessions import MediaSessions
from urmet_gateway.usecases.state import StateReader


class DoorphoneService:
    """Ring, view, open, hang up and talk, told as coroutines over the current client.

    Build it on the event loop it serves: it captures that loop to spawn the
    session teardown a terminal call state triggers.
    """

    def __init__(
        self,
        *,
        port: DoorphonePort,
        bus: EventBus,
        clock: Clock,
        factory: SessionFactory | None = None,
    ) -> None:
        self._port = port
        self._bus = bus
        self._now = clock
        self._calls = CallBook()
        self._media = MediaSessions(
            factory=factory,
            calls=self._calls,
            sink=bus,
            clock=clock,
            on_change=self.publish_state,
        )
        self._state = StateReader(
            port=port,
            calls_views=self._calls.views,
            sessions_views=self._media.views,
            mic_muted=lambda: self._mic_muted,
        )
        # Muted until a page asks to talk: a visitor is not spoken to before
        # anyone chose to answer. The stack is realigned to this every time the
        # supervisor brings a fresh client up (``realign``).
        self._mic_muted = True
        # How many INVITEs of ours are in flight. A dialog first seen while one
        # is, is ours; a ring already seen for that id overrules the guess.
        self._inviting = 0

    @property
    def media(self) -> MediaSessions:
        """The browser legs bridged onto the live calls, for the signalling routes."""
        return self._media

    # -- lifecycle steps the runtime drives -------------------------------

    async def realign(self) -> None:
        """Re-apply the owned microphone state onto the client that just came up.

        A fresh client comes up with the near end open. The supervisor calls this
        after each connect, so a reconnect can never leave the panel able to hear
        the room around the server. Publishing state is part of ``set_mic_muted``.
        """
        await self.set_mic_muted(self._mic_muted)

    async def close_sessions(self) -> None:
        """Close every browser leg, first in the shutdown order (DESIGN 5.5)."""
        await self._media.aclose()

    def clear_calls(self) -> None:
        """Forget every live dialog, after the client has been stopped."""
        self._calls.clear()

    # -- reads ------------------------------------------------------------

    def state(self) -> StateView:
        """A snapshot of what the interface draws, without crossing the worker."""
        return self._state.snapshot()

    # -- actions ----------------------------------------------------------

    async def place_call(self, *, want_video: bool = True) -> str:
        """INVITE the doorphone and return the call id once its media streams."""
        call = await self._invite(want_video=want_video)
        self._calls.record(call, CallState.STREAMING, Direction.OUTGOING, refine_only=True)
        self.publish_state()
        return call.id

    async def answer(self, call_id: str) -> None:
        """Answer an inbound doorbell and wait until its media streams."""
        call = self._calls.handle(call_id)
        await self._port.answer(call)
        self._calls.record(call, CallState.STREAMING, Direction.INCOMING, refine_only=True)
        self.publish_state()

    async def hangup(self, call_id: str) -> None:
        """End a dialog, and the browser leg on it. Idempotent.

        The session goes first and is waited for, so the taps are released before
        the dialog they were armed on is torn down.
        """
        tracked = self._calls.find(call_id)
        if tracked is None:
            return
        await self._media.close_for_call(call_id)
        await self._port.hangup(tracked.handle)
        self._calls.forget(call_id)
        self.publish_state()

    async def set_mic_muted(self, muted: bool) -> None:
        """Decide whether the doorphone can hear this end at all."""
        await self._port.set_mic_muted(muted)
        self._mic_muted = muted
        self.publish_state()

    async def open(self, actuator: ActuatorName) -> None:
        """Drive an actuator, and report only an open the panel acknowledged.

        One action, whatever the moment: while a call streams the INFO travels
        inside that live dialog, otherwise the SDK places a short call of its own
        and releases it. The caller never chooses between the two. Raises
        ``OpenNotAcknowledgedError`` when the panel stayed silent or answered
        non-200, published as unknown rather than open, and never retried.
        """
        streaming = self._calls.streaming()
        try:
            if streaming:
                await self._port.open_during(streaming[0].handle, actuator.signal)
            else:
                await self._open_on_demand(actuator)
        except OpenNotAcknowledgedError:
            self._publish(OpenEvent(at=self._now(), actuator=actuator, acknowledged=False))
            raise
        self._publish(OpenEvent(at=self._now(), actuator=actuator, acknowledged=True))

    async def offer(self, sdp: str, call_id: str | None) -> SessionAnswer:
        """Bridge a live call into the browser that sent this offer."""
        return await self._media.answer(sdp, call_id)

    async def close_session(self, session_id: str) -> None:
        """End one browser leg. Idempotent."""
        await self._media.close_session(session_id)

    # -- the callbacks, already on the loop -------------------------------

    def ring_arrived(self, event: SdkRingEvent) -> None:
        """The panel rang. Marshalled onto the loop by the bridge before it lands."""
        self._calls.mark_incoming(event.call_id)
        self._publish(
            RingEvent(
                at=self._now(),
                doorphone=DoorphoneView.of(event.doorphone),
                call_id=event.call_id,
            )
        )

    def call_state_arrived(self, call: CallHandle, state: CallState) -> None:
        """A dialog moved. Marshalled onto the loop by the bridge before it lands."""
        side = Direction.OUTGOING if self._inviting else Direction.INCOMING
        if not self._calls.record(call, state, side):
            return
        tracked = self._calls.find(call.id)
        direction = tracked.direction if tracked is not None else side
        self._publish(CallEvent(at=self._now(), call_id=call.id, state=state, direction=direction))
        if state in TERMINAL_STATES:
            self._media.call_ended(call.id)
            self._calls.forget(call.id)
            self.publish_state()

    # -- helpers ----------------------------------------------------------

    async def _invite(self, *, want_video: bool) -> CallHandle:
        self._inviting += 1
        try:
            return await self._port.view_door(want_video=want_video)
        finally:
            self._inviting -= 1

    async def _open_on_demand(self, actuator: ActuatorName) -> None:
        self._inviting += 1
        try:
            await self._port.open_on_demand(actuator.signal)
        finally:
            self._inviting -= 1

    def _publish(self, event: Event) -> None:
        """Publish an event, then the state that follows every event."""
        self._bus.publish(event)
        self.publish_state()

    def publish_state(self) -> None:
        """Publish the one snapshot every reader and every event is made of."""
        self._bus.publish(StateEvent.of(self._state.snapshot(), self._now()))
