"""Typed mirrors of the gateway state wire model (DESIGN 5.2).

These are plain frozen dataclasses, not pydantic: the integration declares no
requirements (manifest ``requirements: []``) and must not add one. Every model
carries a ``from_dict`` that accepts the JSON the gateway sends and is forgiving
of a field the gateway adds later, so a gateway ahead of the integration never
crashes the event loop.

The event models that travel over ``GET /api/events`` live in ``events.py`` and
import the state models from here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Final

from homeassistant.util import dt as dt_util


def parse_at(data: Mapping[str, Any]) -> datetime | None:
    """Parse the ``at`` field every event carries (ISO 8601 UTC)."""
    raw = data.get("at")
    return dt_util.parse_datetime(raw) if isinstance(raw, str) else None


class CallState(StrEnum):
    """Where a dialog stands, mirroring the gateway's ``CallState`` (DESIGN 5.2).

    ``UNKNOWN`` is where a value this build does not know lands, i.e. a gateway
    ahead of the integration. It is a named member rather than a raw string kept
    verbatim, so a comparison against the vocabulary can never quietly miss.
    """

    IDLE = "idle"
    RINGING = "ringing"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    ENDED = "ended"
    ERROR = "error"
    UNKNOWN = "unknown"

    @property
    def is_active(self) -> bool:
        """Ringing, connecting or streaming: the panel is engaged (DESIGN 6.5)."""
        return self in ACTIVE_CALL_STATES

    @classmethod
    def _missing_(cls, value: object) -> CallState:
        return cls.UNKNOWN


ACTIVE_CALL_STATES: Final = frozenset(
    {CallState.RINGING, CallState.CONNECTING, CallState.STREAMING}
)


class CallDirection(StrEnum):
    """Which side placed a dialog: the panel rang us, or we called the panel."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> CallDirection:
        return cls.UNKNOWN


class SessionState(StrEnum):
    """Where a browser media leg stands, mirroring the gateway (DESIGN 5.2)."""

    OPEN = "open"
    WAITING = "waiting"
    DEGRADED = "degraded"
    CLOSED = "closed"
    UNKNOWN = "unknown"

    @property
    def is_faulted(self) -> bool:
        """Lost a half or gone: the state a session reason is worth reporting for."""
        return self in {SessionState.DEGRADED, SessionState.CLOSED}

    @classmethod
    def _missing_(cls, value: object) -> SessionState:
        return cls.UNKNOWN


@dataclass(frozen=True, slots=True)
class DoorphoneView:
    """The panel the gateway is bound to. Null until one is configured or rings."""

    mac: str
    name: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DoorphoneView:
        return cls(mac=str(data["mac"]), name=str(data.get("name", "")))


@dataclass(frozen=True, slots=True)
class CallView:
    """A live dialog: what it is doing, and who placed it."""

    id: str
    state: CallState
    direction: CallDirection

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CallView:
        return cls(
            id=str(data["id"]),
            state=CallState(data.get("state", "")),
            direction=CallDirection(data.get("direction", "")),
        )


@dataclass(frozen=True, slots=True)
class VideoStats:
    """Per-session video counters. Null whenever there is no picture."""

    width: int
    height: int
    packets_sent: int
    packets_dropped: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VideoStats:
        return cls(
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            packets_sent=int(data.get("packets_sent", 0)),
            packets_dropped=int(data.get("packets_dropped", 0)),
        )


@dataclass(frozen=True, slots=True)
class AudioStats:
    """Per-session audio counters, named from the doorphone outward (DESIGN 5.2)."""

    from_doorphone: int
    to_browser: int
    to_doorphone: int
    silence_sent: int
    partial_from_doorphone: int
    dropped_from_doorphone: int
    dropped_to_doorphone: int
    max_callback_ms: float
    budget_ms: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AudioStats:
        return cls(
            from_doorphone=int(data.get("from_doorphone", 0)),
            to_browser=int(data.get("to_browser", 0)),
            to_doorphone=int(data.get("to_doorphone", 0)),
            silence_sent=int(data.get("silence_sent", 0)),
            partial_from_doorphone=int(data.get("partial_from_doorphone", 0)),
            dropped_from_doorphone=int(data.get("dropped_from_doorphone", 0)),
            dropped_to_doorphone=int(data.get("dropped_to_doorphone", 0)),
            max_callback_ms=float(data.get("max_callback_ms", 0.0)),
            budget_ms=float(data.get("budget_ms", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class SessionView:
    """A browser media leg, and what is flowing through it."""

    session_id: str
    call_id: str
    state: SessionState
    connection: str
    reason: str
    video: VideoStats | None
    audio: AudioStats | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SessionView:
        video = data.get("video")
        audio = data.get("audio")
        return cls(
            session_id=str(data["session_id"]),
            call_id=str(data.get("call_id", "")),
            state=SessionState(data.get("state", "")),
            connection=str(data.get("connection", "")),
            reason=str(data.get("reason", "")),
            video=VideoStats.from_dict(video) if isinstance(video, Mapping) else None,
            audio=AudioStats.from_dict(audio) if isinstance(audio, Mapping) else None,
        )


@dataclass(frozen=True, slots=True)
class StateView:
    """The whole of GET /api/state; the coordinator's data model."""

    registered: bool
    doorphone: DoorphoneView | None
    calls: tuple[CallView, ...]
    mic_muted: bool
    sessions: tuple[SessionView, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StateView:
        doorphone = data.get("doorphone")
        return cls(
            registered=bool(data.get("registered", False)),
            doorphone=(
                DoorphoneView.from_dict(doorphone) if isinstance(doorphone, Mapping) else None
            ),
            calls=tuple(
                CallView.from_dict(c) for c in data.get("calls", []) if isinstance(c, Mapping)
            ),
            mic_muted=bool(data.get("mic_muted", False)),
            sessions=tuple(
                SessionView.from_dict(s) for s in data.get("sessions", []) if isinstance(s, Mapping)
            ),
        )
