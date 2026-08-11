"""No SIP callback body runs on the event loop.

The bridge is the single hop out of the SDK. This scenario drives a real
``UrmetClient`` over the SDK doubles, whose callbacks are delivered from a worker
thread exactly as a native stack delivers them, and proves that every callback
body executes off the event loop while only the marshalled handlers run on it.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from urmet_sdk import CallHandle, CallState, RingEvent

from urmet_gateway.sip import CallbackBridge, SdkWorker

from .conftest import Harness


class _ProbedBridge(CallbackBridge):
    """A bridge that records the thread every SDK callback body ran on."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.sdk_threads: list[int] = []

    def _ring(self, event: RingEvent) -> None:
        self.sdk_threads.append(threading.get_ident())
        super()._ring(event)

    def _call_state(self, call: CallHandle, state: CallState) -> None:
        self.sdk_threads.append(threading.get_ident())
        super()._call_state(call, state)


@pytest.mark.asyncio
async def test_no_callback_body_runs_on_the_event_loop(harness: Harness) -> None:
    loop = asyncio.get_running_loop()
    loop_ident = threading.get_ident()
    worker = SdkWorker()

    ring_threads: list[int] = []
    call_threads: list[int] = []
    ring_seen = asyncio.Event()
    streaming_seen = asyncio.Event()
    ended_seen = asyncio.Event()

    def on_ring(_event: RingEvent) -> None:
        ring_threads.append(threading.get_ident())
        ring_seen.set()

    def on_call(_call: CallHandle, state: CallState) -> None:
        call_threads.append(threading.get_ident())
        if state == CallState.STREAMING:
            streaming_seen.set()
        elif state == CallState.ENDED:
            ended_seen.set()

    bridge = _ProbedBridge(loop=loop, on_ring=on_ring, on_call=on_call)
    client = harness.build_client()
    bridge.bind(client)
    await worker.run(client.start)

    # The doorbell rings: on_ring first, then RINGING.
    call = await worker.run(harness.transport.simulate_ring, harness.doorphone)
    await asyncio.wait_for(ring_seen.wait(), timeout=2.0)

    # Answer, so the dialog streams.
    await worker.run(client.answer, call)
    await asyncio.wait_for(streaming_seen.wait(), timeout=2.0)

    # Hang up, so the dialog ends.
    await worker.run(client.hangup, call)
    await asyncio.wait_for(ended_seen.wait(), timeout=2.0)

    # Every SDK callback body ran off the loop; only the marshalled handlers ran on it.
    assert bridge.sdk_threads, "no SDK callback was delivered"
    assert all(ident != loop_ident for ident in bridge.sdk_threads)
    assert ring_threads and all(ident == loop_ident for ident in ring_threads)
    assert call_threads and all(ident == loop_ident for ident in call_threads)

    await worker.aclose()
