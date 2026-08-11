"""The vocabulary the gateway speaks on its own wire.

The types the Home Assistant integration reads, named for what they mean to a
caller rather than for how the SDK stores them. Nothing here knows about HTTP,
WebRTC or the native stack, and nothing holds a native handle. Every model is
frozen: a snapshot is a reading, not a thing to edit in place. The event
envelopes match the WebSocket contract one for one, and a ``state`` event follows
every other event, so a subscriber's view can never disagree with what it saw.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from urmet_sdk import Actuator, CallState, Doorphone


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Direction(StrEnum):
    """Which side placed a dialog: the panel rang us, or we called the panel."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"


class ActuatorName(StrEnum):
    """What an open opens, named for the thing rather than for its DTMF signal."""

    DOOR = "door"
    GATE = "gate"

    @property
    def signal(self) -> Actuator:
        """The SDK actuator carrying the ``Signal=`` value this name stands for."""
        return Actuator.DOOR if self is ActuatorName.DOOR else Actuator.GATE


class SessionState(StrEnum):
    """Where a session stands: open, still coming (waiting), lost a half
    (degraded), or closed. A missing picture never ends a call."""

    OPEN = "open"
    WAITING = "waiting"
    DEGRADED = "degraded"
    CLOSED = "closed"


class DoorphoneView(_Frozen):
    """A street panel: its MAC, and the name it was given if it has one."""

    mac: str
    name: str = ""

    @classmethod
    def of(cls, doorphone: Doorphone) -> DoorphoneView:
        """Read the SDK's doorphone into the shape the interface draws."""
        return cls(mac=doorphone.mac, name=doorphone.name)


class CallView(_Frozen):
    """One live dialog: what it is doing and who started it."""

    id: str
    state: CallState
    direction: Direction


class VideoFlow(_Frozen):
    """What the picture is really doing, rather than what was asked for."""

    width: int
    height: int
    packets_sent: int = 0
    packets_dropped: int = 0


class AudioFlow(_Frozen):
    """The voice, counted at the doorphone's clock: only ``to_browser`` says the
    far end is fed, and ``silence_sent`` is correct output for a muted page."""

    from_doorphone: int = 0
    to_browser: int = 0
    to_doorphone: int = 0
    silence_sent: int = 0
    partial_from_doorphone: int = 0
    dropped_from_doorphone: int = 0
    dropped_to_doorphone: int = 0
    max_callback_ms: float = 0.0
    budget_ms: float = 0.0


class SessionView(_Frozen):
    """One session: what it is tied to, and what is flowing through it.
    ``connection`` is aiortc's own word; ``video`` is null when no picture flows."""

    session_id: str
    call_id: str
    state: SessionState
    connection: str
    reason: str = ""
    video: VideoFlow | None = None
    audio: AudioFlow | None = None


class SessionAnswer(_Frozen):
    """What a browser's offer is answered with: the session, and the SDP."""

    session_id: str
    call_id: str
    type: Literal["answer"] = "answer"
    sdp: str


class StateView(_Frozen):
    """Everything the interface draws. ``doorphone`` is null until a panel is
    known; ``calls`` and ``sessions`` are empty, never null."""

    registered: bool
    doorphone: DoorphoneView | None = None
    calls: list[CallView] = Field(default_factory=list)
    mic_muted: bool = False
    sessions: list[SessionView] = Field(default_factory=list)


class EventType(StrEnum):
    """The ``type`` field that tells a subscriber which event it received."""

    STATE = "state"
    RING = "ring"
    CALL = "call"
    OPEN = "open"
    REGISTRATION = "registration"
    WEBRTC = "webrtc"


class Event(_Frozen):
    """What every event carries: the instant it happened, UTC."""

    at: datetime


class StateEvent(StateView, Event):
    """A full snapshot, sent once on connect and again after every event."""

    type: Literal[EventType.STATE] = EventType.STATE

    @classmethod
    def of(cls, state: StateView, at: datetime) -> StateEvent:
        """Wrap a snapshot into the event that carries it."""
        return cls(at=at, **state.model_dump())


class RingEvent(Event):
    """The panel rang: a dialog is offered and nobody has taken it yet."""

    type: Literal[EventType.RING] = EventType.RING
    doorphone: DoorphoneView
    call_id: str


class CallEvent(Event):
    """A dialog moved: this is where it stands now, and who started it."""

    type: Literal[EventType.CALL] = EventType.CALL
    call_id: str
    state: CallState
    direction: Direction


class OpenEvent(Event):
    """An actuator was driven; ``acknowledged`` false means the state is unknown,
    never that the door stayed shut."""

    type: Literal[EventType.OPEN] = EventType.OPEN
    actuator: ActuatorName
    acknowledged: bool


class RegistrationEvent(Event):
    """The binding changed. ``status_code`` 0 means no SIP response reached this
    layer; ``released`` false is a binding the gateway could not confirm it took
    back."""

    type: Literal[EventType.REGISTRATION] = EventType.REGISTRATION
    registered: bool
    status_code: int = 0
    reason: str = ""
    released: bool = True


class WebrtcEvent(Event):
    """A browser leg opened, lost its picture, or closed."""

    type: Literal[EventType.WEBRTC] = EventType.WEBRTC
    session_id: str
    call_id: str
    state: SessionState
    reason: str = ""


# The discriminated union a serialiser reads to tell the events apart.
GatewayEvent = Annotated[
    StateEvent | RingEvent | CallEvent | OpenEvent | RegistrationEvent | WebrtcEvent,
    Field(discriminator="type"),
]
