"""Reading the gateway's WebSocket event stream in a test.

Two ways to read one subscriber: ``EventStream`` pulls events on demand, either
pinning an exact order (``expect``) or reading past to a causal point (``until``);
``Follower`` reads continuously in a task of its own, for the scenario that needs
another subscriber to keep draining while the one under test stalls.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

import aiohttp
from aiohttp import WSMsgType

RECEIVE_TIMEOUT_S = 10.0
MAX_SKIPPED = 400


class EventStream:
    """One subscriber: reads JSON events, and says what it was looking for."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws
        self.seen: list[dict[str, Any]] = []

    async def expect(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """The next event, which must be this one. Pins an exact ordering."""
        event = await self._next(event_type)
        if not _matches(event, event_type, fields):
            raise AssertionError(f"expected {event_type} {fields}, received {event}")
        return event

    async def until(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """Read past whatever comes first until this event. Pins causal order only."""
        for _ in range(MAX_SKIPPED):
            event = await self._next(event_type)
            if _matches(event, event_type, fields):
                return event
        raise AssertionError(f"never received {event_type} in {MAX_SKIPPED} events; {self.seen!r}")

    async def closing_code(self) -> int:
        """Drain the stream to its end and answer the close code it carried."""
        for _ in range(MAX_SKIPPED):
            message = await self._ws.receive(timeout=RECEIVE_TIMEOUT_S)
            if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                code = self._ws.close_code
                assert code is not None, "the stream ended without a close code"
                return code
        raise AssertionError("the stream never closed")

    async def _next(self, wanted: str) -> dict[str, Any]:
        try:
            message = await self._ws.receive(timeout=RECEIVE_TIMEOUT_S)
        except TimeoutError:
            raise AssertionError(
                f"never received {wanted}; the stream carried {self.seen!r}"
            ) from None
        assert message.type is WSMsgType.TEXT, f"expected {wanted}, the stream sent {message.type}"
        event: dict[str, Any] = json.loads(message.data)
        self.seen.append(event)
        return event


class Follower:
    """A subscriber somebody is actually reading, continuously, in a task of its own."""

    def __init__(self, stream: EventStream) -> None:
        self._stream = stream
        self._received: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pump = asyncio.create_task(self._read_forever(), name="follower")

    async def until(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """The next received event of this shape, past anything else it received."""
        for _ in range(MAX_SKIPPED):
            event = await asyncio.wait_for(self._received.get(), RECEIVE_TIMEOUT_S)
            if _matches(event, event_type, fields):
                return event
        raise AssertionError(f"no {event_type} matching {fields} reached the follower")

    async def stop(self) -> None:
        self._pump.cancel()
        with suppress(asyncio.CancelledError):
            await self._pump

    async def _read_forever(self) -> None:
        while True:
            await self._received.put(await self._stream._next("an event"))


def _matches(event: dict[str, Any], event_type: str, fields: dict[str, Any]) -> bool:
    return event["type"] == event_type and all(event.get(k) == v for k, v in fields.items())
