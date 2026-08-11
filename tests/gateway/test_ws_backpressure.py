"""A subscriber that stops reading is dropped 1013, and nothing else is.

The publisher that must never wait is the SIP worker thread: a stall there stalls
the stack, and the doorbell with it. So every subscriber gets a bounded queue of
its own, and the one that stops reading is dropped once it overflows while the
others carry on. Making that happen needs real backpressure, so the server's send
buffer is pinned small and the bus built small: a subscriber that never reads then
fills its pipe within a handful of events, and one that is read never does.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import pytest
from aiohttp import WSCloseCode

from urmet_gateway.domain.models import RegistrationEvent

from .http_support import Follower, HttpHarness, http_harness

# Two events exceed the pinned send buffer plus the peer's receive window, so the
# writer to a reader that stopped blocks within a couple of sends; each is small
# enough that a reader that keeps up drains it over loopback before the next one.
EVENT_BYTES = 64 * 1024
SEND_BUFFER = 4096
BUS_CAPACITY = 16
EVENTS = 40
DROPPED = "subscriber dropped"


async def test_a_subscriber_that_stops_reading_is_dropped_and_the_others_are_not(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with http_harness(bus_capacity=BUS_CAPACITY, send_buffer=SEND_BUFFER) as h:
        await h.wait_registered()

        async with h.events() as stalled, h.events() as kept_up_stream:
            kept_up = Follower(kept_up_stream)
            try:
                with caplog.at_level(logging.WARNING, logger="urmet_gateway.usecases.events"):
                    for index in range(EVENTS):
                        h.bus.publish(_big_event(h, index))
                        await asyncio.sleep(0.02)
                    for _ in range(10):
                        await asyncio.sleep(0.01)

                drops = [r for r in caplog.records if DROPPED in r.getMessage()]
                assert len(drops) == 1, [r.getMessage() for r in caplog.records]

                # The one being read is still in its place: it takes the next event.
                h.bus.publish(_marker(h))
                assert await kept_up.until("registration", reason="MARKER")
            finally:
                await kept_up.stop()

            # Read the stalled one at last: it is told why it was closed.
            assert await stalled.closing_code() == WSCloseCode.TRY_AGAIN_LATER

        # Nothing else was harmed: the gateway still answers and still gives a new
        # subscriber the whole state.
        state = await h.get("/api/state")
        assert state.status == 200
        async with h.events() as fresh:
            assert (await fresh.expect("state"))["registered"] is True


def _big_event(h: HttpHarness, index: int) -> RegistrationEvent:
    return RegistrationEvent(
        at=_now(h), registered=True, status_code=200, reason=f"{index}-{'x' * EVENT_BYTES}"
    )


def _marker(h: HttpHarness) -> RegistrationEvent:
    return RegistrationEvent(at=_now(h), registered=False, status_code=0, reason="MARKER")


def _now(h: HttpHarness) -> datetime:
    clock: datetime = h.harness.clock()
    return clock
