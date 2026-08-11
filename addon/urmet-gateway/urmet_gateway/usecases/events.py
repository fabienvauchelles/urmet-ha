"""Fan-out of the event stream: one bounded queue per subscriber.

Two properties decide this design. A publisher never waits, because a publisher
may be a callback hop and a stall there stalls what called it. And a subscriber
that stops reading harms nobody but itself: its queue fills, it is dropped with a
log line, and every other subscriber carries on. The crossing from a foreign
thread to the loop belongs here, so a publisher on another thread hops once
through ``call_soon_threadsafe`` and returns.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable
from types import TracebackType

from urmet_gateway.domain.models import Event

logger = logging.getLogger(__name__)

# Events a subscriber may fall behind by before it is dropped. One that keeps up
# never holds more than one or two.
DEFAULT_CAPACITY = 64


class EventBusClosedError(RuntimeError):
    """A subscription was asked for after the bus had been closed."""


class Subscription:
    """One subscriber's bounded queue, iterated until the bus closes it."""

    def __init__(self, capacity: int, release: Callable[[Subscription], None]) -> None:
        self._capacity = capacity
        # One slot past capacity is reserved for the closing sentinel, so an
        # overflowed queue can still say so to its consumer.
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue(capacity + 1)
        self._release = release
        self._closed = False
        self._dropped = False

    @property
    def dropped(self) -> bool:
        """Whether this subscriber was dropped for falling too far behind."""
        return self._dropped

    def __enter__(self) -> Subscription:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    async def __aiter__(self) -> AsyncIterator[Event]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    def offer(self, event: Event) -> bool:
        """Queue ``event`` without waiting. False when there was no room left."""
        if self._closed or self._queue.qsize() >= self._capacity:
            return False
        self._queue.put_nowait(event)
        return True

    def close(self, *, dropped: bool = False) -> None:
        """End the iteration and leave the bus. Idempotent."""
        if self._closed:
            return
        self._closed = True
        self._dropped = dropped
        self._queue.put_nowait(None)
        self._release(self)


class EventBus:
    """Publishes an event to every subscriber, from any thread, without waiting.

    Built on the event loop it serves. A publish from the loop is delivered there
    and then; a publish from another thread hops once through
    ``call_soon_threadsafe``, the only thing a foreign-thread callback may do.
    """

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY) -> None:
        self._loop = asyncio.get_running_loop()
        self._loop_thread_id = threading.get_ident()
        self._capacity = capacity
        self._subscribers: set[Subscription] = set()
        self._closed = False

    def subscribe(self) -> Subscription:
        """Open a subscription with a queue of its own. Call it from the loop."""
        if self._closed:
            raise EventBusClosedError("the event bus is closed; the gateway is shutting down")
        subscription = Subscription(self._capacity, self._subscribers.discard)
        self._subscribers.add(subscription)
        return subscription

    def publish(self, event: Event) -> None:
        """Hand ``event`` to every subscriber. Safe from any thread, never blocks."""
        if self._closed:
            return
        if threading.get_ident() == self._loop_thread_id:
            self._fan_out(event)
            return
        try:
            self._loop.call_soon_threadsafe(self._fan_out, event)
        except RuntimeError:
            # The loop is gone: a shutdown raced a callback. Nothing is left to
            # deliver to, and raising here would unwind into the native stack.
            logger.debug("%s dropped: the event loop is closed", type(event).__name__)

    def close(self) -> None:
        """Close every subscription, ending each ``async for``. Idempotent."""
        if self._closed:
            return
        self._closed = True
        for subscription in list(self._subscribers):
            subscription.close()

    def _fan_out(self, event: Event) -> None:
        """Deliver on the loop thread, dropping whoever has stopped reading."""
        for subscription in list(self._subscribers):
            if subscription.offer(event):
                continue
            logger.warning("subscriber dropped: it fell more than %d events behind", self._capacity)
            subscription.close(dropped=True)
