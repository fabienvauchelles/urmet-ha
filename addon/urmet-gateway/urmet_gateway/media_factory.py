"""The real WebRTC session factory: the seam the offer route depends on.

A composition-root module, sibling to ``main``. It is the one place that binds a
live call to the two adapters a media session needs: the sip layer's ``WorkerTap``,
which crosses the SDK's ``MediaTap`` on the single worker thread, and the media
layer's ``MediaSession``, which owns the aiortc peer connection. Neither adapter
knows the other exists; here is where they are put together, once per call.

The transport is resolved lazily through ``tap`` at create time rather than captured
at boot, because a lost binding is recovered by building a new ``PjsipTransport``
whole (``stop`` is terminal), and the call an offer names belongs to whatever
transport is current now, not the one alive when the gateway started.
"""

from __future__ import annotations

from collections.abc import Callable

from urmet_sdk import CallHandle, MediaTap

from urmet_gateway.domain.ports import MediaChanged, MediaSessionPort, SessionClosed
from urmet_gateway.media.session import MediaSession
from urmet_gateway.sip import SdkWorker, WorkerTap

TapProvider = Callable[[], MediaTap]


class MediaSessionFactory:
    """Builds a ``MediaSession`` for a live call over the current transport."""

    def __init__(self, *, tap: TapProvider, worker: SdkWorker, video_settle_s: float) -> None:
        self._tap = tap
        self._worker = worker
        self._settle_s = video_settle_s

    def create(
        self,
        *,
        session_id: str,
        call: CallHandle,
        on_closed: SessionClosed,
        on_media_change: MediaChanged,
    ) -> MediaSessionPort:
        """Bind the call to a worker tap and hand back a session over it."""
        worker_tap = WorkerTap(self._tap(), self._worker, call)
        return MediaSession(
            session_id=session_id,
            call_id=call.id,
            tap=worker_tap,
            video_settle_s=self._settle_s,
            on_closed=on_closed,
            on_media_change=on_media_change,
        )
