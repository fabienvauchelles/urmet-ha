"""Out of the SDK, onto the event loop, in exactly one hop.

Every SIP callback fires on a native worker thread and must give that thread
back at once: the stack needs it, and an exception unwinding into the C++ frames
that called us would abort the process. So each callback here does exactly one
thing, ``loop.call_soon_threadsafe``, and returns. No await and no work: the
loop-side handlers own everything that follows, including the call book that is
the single authority on which id maps to which handle.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Protocol

from urmet_sdk import CallHandle, CallState, RingEvent

logger = logging.getLogger(__name__)

RingHandler = Callable[[RingEvent], None]
CallStateHandler = Callable[[CallHandle, CallState], None]


class DoorbellSource(Protocol):
    """The subset of the SDK client the bridge subscribes to.

    ``UrmetClient`` satisfies it structurally. The bridge names this Protocol
    rather than the client so the SIP adapter never depends on the composition
    root's concrete transport.
    """

    def on_ring(self, cb: RingHandler) -> None: ...
    def on_call_state(self, cb: CallStateHandler) -> None: ...


class CallbackBridge:
    """Marshals the two SIP callbacks onto the loop, one hop each.

    Build it on the loop it serves, bind it to a client before that client
    registers, and give it the two loop-side handlers it hands the work to. The
    handlers run on the event loop; nothing else here does.
    """

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        on_ring: RingHandler,
        on_call: CallStateHandler,
    ) -> None:
        self._loop = loop
        self._on_ring = on_ring
        self._on_call = on_call

    def bind(self, client: DoorbellSource) -> None:
        """Subscribe to a client's ring and call-state callbacks.

        Each SDK callback slot holds one handler, so binding a fresh client
        after a reconnect points the SDK at this bridge again and drops the old
        client's slot with it.
        """
        client.on_ring(self._ring)
        client.on_call_state(self._call_state)

    # -- the SIP worker thread: one hop, and return ------------------------

    def _ring(self, event: RingEvent) -> None:
        """Fired on the SIP worker thread. Hop and return."""
        self._hop(self._on_ring, event)

    def _call_state(self, call: CallHandle, state: CallState) -> None:
        """Fired on the SIP worker thread. Hop and return."""
        self._hop(self._on_call, call, state)

    def _hop(self, handler: Callable[..., None], *args: object) -> None:
        """Hand ``handler`` to the loop. Never raises into the native stack."""
        try:
            self._loop.call_soon_threadsafe(handler, *args)
        except RuntimeError:
            # Shutdown raced the SIP stack. Nothing is listening any more, and
            # unwinding into the C++ frames that called us would end the process.
            logger.debug("SIP event dropped: the event loop is closed")
