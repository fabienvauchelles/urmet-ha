"""The event stream: one WebSocket per subscriber, the full state first.

A subscriber gets a snapshot the moment it connects and every event afterwards,
so a page never has to ask for the state it just missed. Nothing is lost between
the two: the subscription is registered before the snapshot is read, so anything
published from that instant on is already queued behind it. A state event that
lands in the gap is a replay, not a contradiction, because a state event carries
the whole view and the bus keeps publication order.

Nothing on this stream is a command. A frame the client sends is read, so a close
or a pong is noticed at once, and then dropped. A subscriber that stops reading is
dropped rather than tolerated: its queue is bounded by the bus, the write buffer
here is kept small so backpressure reaches that queue, and the one that overflows
is closed 1013 while every other one carries on.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from aiohttp import WSCloseCode, WSMsgType, web

from urmet_gateway.constants import WS_HEARTBEAT_S, WS_WRITER_LIMIT
from urmet_gateway.domain.errors import EventBusClosedError
from urmet_gateway.domain.models import Event, StateEvent
from urmet_gateway.usecases import DoorphoneService, EventBus, Subscription

logger = logging.getLogger(__name__)

BEHIND = "the event stream fell behind"
SHUTTING_DOWN = "the gateway is shutting down"
FAILED = "the event stream failed"


class EventsApi:
    """``GET /api/events``: the state on connect, then every event as it happens."""

    def __init__(
        self,
        service: DoorphoneService,
        bus: EventBus,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self._service = service
        self._bus = bus
        self._now = clock

    def routes(self) -> list[web.RouteDef]:
        """The single route this module owns."""
        return [web.get("/api/events", self.subscribe)]

    async def subscribe(self, request: web.Request) -> web.WebSocketResponse:
        """Serve one subscriber until it leaves, is dropped, or the bus closes.

        Nothing raised here reaches the error middleware: the response is already
        on the wire, so a client going away is logged and closed, not answered.
        """
        ws = web.WebSocketResponse(heartbeat=WS_HEARTBEAT_S, writer_limit=WS_WRITER_LIMIT)
        await ws.prepare(request)
        try:
            subscription = self._bus.subscribe()
        except EventBusClosedError:
            await ws.close(code=WSCloseCode.GOING_AWAY, message=SHUTTING_DOWN.encode())
            return ws
        failed = False
        try:
            with subscription:
                await _either(self._stream(ws, subscription), _read(ws))
        except ConnectionResetError:
            logger.debug("event stream closed by the client")
        except Exception:
            logger.exception("event stream failed")
            failed = True
        code, message = _farewell(subscription, failed=failed)
        await ws.close(code=code, message=message)
        return ws

    async def _stream(self, ws: web.WebSocketResponse, subscription: Subscription) -> None:
        """Send the snapshot, then everything published until the bus closes."""
        await _send(ws, StateEvent.of(self._service.state(), self._now()))
        async for event in subscription:
            if subscription.dropped:
                return
            await _send(ws, event)


async def _send(ws: web.WebSocketResponse, event: Event) -> None:
    """One event, one message, serialised the way the REST bodies are."""
    await ws.send_str(event.model_dump_json())


async def _read(ws: web.WebSocketResponse) -> None:
    """Drain what the client sends, so a close or a pong is noticed at once."""
    async for message in ws:
        if message.type is WSMsgType.ERROR:
            logger.warning("event stream failed: %s", ws.exception())
            return
        logger.debug("ignored a %s frame on the event stream", message.type.name)


async def _either(*sides: Coroutine[Any, Any, None]) -> None:
    """Run both sides, stop at the first one to end, and raise what ended it."""
    tasks = [asyncio.create_task(side, name=f"urmet-ws-{side.__qualname__}") for side in sides]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    for task in done:
        task.result()


def _farewell(subscription: Subscription, *, failed: bool) -> tuple[int, bytes]:
    """Why the stream ended, told in the close frame rather than left to guess."""
    if failed:
        return WSCloseCode.INTERNAL_ERROR, FAILED.encode()
    if subscription.dropped:
        return WSCloseCode.TRY_AGAIN_LATER, BEHIND.encode()
    return WSCloseCode.GOING_AWAY, SHUTTING_DOWN.encode()
