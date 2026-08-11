"""The browser legs bridged onto the live calls, one session per call.

A session is built with a call and torn down with it. That policy lives here
rather than in the media layer because deciding which dialog an offer belongs to
needs the book of live calls, and telling the world what happened needs the event
stream. Three things end a session: a close request, the browser leg failing, and
the dialog ending underneath it. All three land here, all three publish the same
event, and none leaves a native tap armed on a call that is over.

A picture that stops is not one of them. A doorphone you can talk to but not see
is worth more than one that hung up on you, so a stalled video leaves the session
degraded with a reason and the voice carries on. Nothing here names aiortc: it
reaches the media through the ``SessionFactory`` port and reads back a view.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from contextlib import suppress
from typing import Any

from urmet_sdk import CallHandle, CallState

from urmet_gateway.domain.errors import MediaUnavailableError, NoStreamingCallError
from urmet_gateway.domain.models import SessionAnswer, SessionView, WebrtcEvent
from urmet_gateway.domain.ports import Clock, EventSink, MediaSessionPort, SessionFactory
from urmet_gateway.usecases.calls import CallBook

logger = logging.getLogger(__name__)

REPLACED = "the browser offered again on this call"
ENDED_BY_CLIENT = "the client ended the session"
CALL_ENDED = "the call ended"
SHUTTING_DOWN = "the gateway is shutting down"


class MediaSessions:
    """Opens, watches and closes the browser legs bridged onto the live calls."""

    def __init__(
        self,
        *,
        factory: SessionFactory | None,
        calls: CallBook,
        sink: EventSink,
        clock: Clock,
        on_change: Callable[[], None],
    ) -> None:
        self._factory = factory
        self._calls = calls
        self._sink = sink
        self._now = clock
        self._on_change = on_change
        self._loop = asyncio.get_running_loop()
        self._sessions: dict[str, MediaSessionPort] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._opened = 0

    def views(self) -> list[SessionView]:
        """One entry per session still up, with what is really flowing in it."""
        return [session.view() for session in self._sessions.values()]

    async def answer(self, sdp: str, call_id: str | None) -> SessionAnswer:
        """Bridge a live call into the browser that sent this offer.

        Without a ``call_id`` the newest streaming call is taken. An offer on a
        call that already has a session replaces it, so a reloaded page comes
        back rather than being refused. Raises ``MediaUnavailableError`` with no
        tap, ``UnknownCallError`` for an unknown id, and ``NoStreamingCallError``
        when nothing carries media yet.
        """
        factory = self._require_factory()
        call = self._pick(call_id)
        await self.close_for_call(call.id, reason=REPLACED)
        self._opened += 1
        session = factory.create(
            session_id=str(self._opened),
            call=call,
            on_closed=self._session_closed,
            on_media_change=self._session_media_changed,
        )
        self._sessions[session.id] = session
        try:
            answer = await session.answer(sdp)
        except Exception as error:
            await session.aclose(reason=f"the offer could not be answered: {error}")
            raise
        self._publish(session)
        self._on_change()
        return SessionAnswer(session_id=session.id, call_id=call.id, sdp=answer)

    async def close_session(self, session_id: str) -> None:
        """End one session. Idempotent: one already gone is already closed."""
        session = self._sessions.get(session_id)
        if session is not None:
            await session.aclose(reason=ENDED_BY_CLIENT)

    async def close_for_call(self, call_id: str, *, reason: str = CALL_ENDED) -> None:
        """End the session on a dialog, and wait until its taps are released.

        What a caller about to hang the dialog up uses, so the native recorder
        and the audio port are gone before the call they were armed on is.
        """
        session = self._for_call(call_id)
        if session is not None:
            await session.aclose(reason=reason)

    def call_ended(self, call_id: str) -> None:
        """The dialog is over, so the session on it is over. Never awaits.

        The callback path has already hopped onto the loop and cannot await, so
        the tearing down happens in a task of its own. The SDK releases the taps
        of a call that ends by itself, so nothing native outlives the dialog
        while this catches up.
        """
        session = self._for_call(call_id)
        if session is not None:
            self._spawn(session.aclose(reason=CALL_ENDED), name=f"urmet-close-{session.id}")

    async def aclose(self) -> None:
        """Close every session and let the tasks still running finish or go."""
        for session in list(self._sessions.values()):
            await session.aclose(reason=SHUTTING_DOWN)
        for task in list(self._tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def _session_closed(self, session: MediaSessionPort, reason: str) -> None:
        """A session ended, however it ended. It leaves the book here and only here."""
        self._sessions.pop(session.id, None)
        self._publish(session, reason=reason)
        self._on_change()

    def _session_media_changed(self, session: MediaSessionPort, reason: str) -> None:
        """A session's picture moved without its call moving: it arrived, or it went."""
        self._publish(session, reason=reason)
        self._on_change()

    def _require_factory(self) -> SessionFactory:
        if self._factory is None:
            raise MediaUnavailableError(
                "this gateway holds no media tap, so no call can be bridged into a browser"
            )
        return self._factory

    def _pick(self, call_id: str | None) -> CallHandle:
        """The dialog an offer belongs to, or the reason there is not one."""
        if call_id is not None:
            tracked = self._calls.require(call_id)
            if tracked.state is not CallState.STREAMING:
                raise NoStreamingCallError(
                    f"call {call_id} is {tracked.state} and carries no media to bridge"
                )
            return tracked.handle
        streaming = self._calls.streaming()
        if not streaming:
            raise NoStreamingCallError(
                "no call is streaming; place one or answer the doorbell before offering"
            )
        return streaming[-1].handle

    def _for_call(self, call_id: str) -> MediaSessionPort | None:
        return next((s for s in self._sessions.values() if s.call_id == call_id), None)

    def _publish(self, session: MediaSessionPort, *, reason: str = "") -> None:
        view = session.view()
        self._sink.publish(
            WebrtcEvent(
                at=self._now(),
                session_id=session.id,
                call_id=session.call_id,
                state=view.state,
                reason=reason or view.reason,
            )
        )

    def _spawn(self, work: Coroutine[Any, Any, None], *, name: str) -> None:
        task = self._loop.create_task(work, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("%s failed", task.get_name(), exc_info=error)
