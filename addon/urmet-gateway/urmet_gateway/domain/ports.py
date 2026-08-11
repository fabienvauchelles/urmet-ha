"""The Protocols the use cases depend on.

This is what keeps the frameworks (aiortc, av) and the native transport out of
the business rules. The use cases name these interfaces only; the sip, media and
composition layers implement them. Every blocking SDK call the ``DoorphonePort``
exposes is already awaitable, and every callback it delivers has already been
marshalled onto the event loop by the adapter behind it, so a use case never
touches a worker thread and never calls ``call_soon_threadsafe`` itself.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from urmet_sdk import (
    Actuator,
    AudioFormat,
    AudioSink,
    CallHandle,
    Doorphone,
    VideoFormat,
)

from urmet_gateway.domain.models import Event, SessionView


class Clock(Protocol):
    """The time a use case stamps its events with. A test freezes it."""

    def __call__(self) -> datetime: ...


class EventSink(Protocol):
    """Where a use case publishes. The bus implements it; a publisher never waits."""

    def publish(self, event: Event) -> None: ...


class DoorphonePort(Protocol):
    """The SIP command surface: blocking calls made awaitable, over the current client.

    Registration is not here: the supervisor owns the binding's whole lifecycle,
    and this port only drives the client it built. Every command resolves the
    current client through the holder the supervisor updates on each rebuild, so a
    reconnect never leaves a command pointing at a dead stack. ``registered`` reads
    that current client without crossing the worker thread.
    """

    @property
    def registered(self) -> bool: ...
    def known_doorphone(self) -> Doorphone | None: ...
    async def view_door(self, *, want_video: bool) -> CallHandle: ...
    async def answer(self, call: CallHandle) -> None: ...
    async def hangup(self, call: CallHandle) -> None: ...
    async def open_during(self, call: CallHandle, actuator: Actuator) -> None: ...
    async def open_on_demand(self, actuator: Actuator) -> None: ...
    async def set_mic_muted(self, muted: bool) -> None: ...


class TapPort(Protocol):
    """A media tap with the thread hop made and one call bound.

    Binding the call here is what keeps a session from ever naming a call that is
    not its own.
    """

    async def open_video(self, sink_path: Path) -> VideoFormat: ...
    async def close_video(self) -> None: ...
    async def attach_audio(self, sink: AudioSink) -> AudioFormat: ...
    async def detach_audio(self) -> None: ...


class MediaSessionPort(Protocol):
    """One browser leg bridged onto one live call."""

    @property
    def id(self) -> str: ...
    @property
    def call_id(self) -> str: ...
    async def answer(self, sdp: str) -> str: ...
    async def aclose(self, *, reason: str) -> None: ...
    def view(self) -> SessionView: ...


SessionClosed = Callable[["MediaSessionPort", str], None]
MediaChanged = Callable[["MediaSessionPort", str], None]


class SessionFactory(Protocol):
    """Builds a media session for a live call, tap and all."""

    def create(
        self,
        *,
        session_id: str,
        call: CallHandle,
        on_closed: SessionClosed,
        on_media_change: MediaChanged,
    ) -> MediaSessionPort: ...
