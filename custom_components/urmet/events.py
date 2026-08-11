"""Typed mirrors of the gateway event stream (DESIGN 5.3).

``parse_event`` turns one decoded ``GET /api/events`` frame into a typed event.
The state models it depends on live in ``models.py``; the coordinator consumes
``StateEvent`` and every other consumer (WP8 event entities, WP9 WebSocket
forwarding) filters on the concrete event classes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .const import (
    EVENT_CALL,
    EVENT_OPEN,
    EVENT_REGISTRATION,
    EVENT_RING,
    EVENT_STATE,
    EVENT_WEBRTC,
)
from .models import CallDirection, CallState, DoorphoneView, SessionState, StateView, parse_at


@dataclass(frozen=True, slots=True)
class StateEvent:
    at: datetime | None
    state: StateView
    type: str = EVENT_STATE


@dataclass(frozen=True, slots=True)
class RingEvent:
    at: datetime | None
    doorphone: DoorphoneView | None
    call_id: str | None
    type: str = EVENT_RING


@dataclass(frozen=True, slots=True)
class CallEvent:
    at: datetime | None
    call_id: str
    state: CallState
    direction: CallDirection | None
    type: str = EVENT_CALL


@dataclass(frozen=True, slots=True)
class OpenEvent:
    at: datetime | None
    actuator: str
    acknowledged: bool
    call_id: str | None
    type: str = EVENT_OPEN


@dataclass(frozen=True, slots=True)
class RegistrationEvent:
    at: datetime | None
    registered: bool
    status_code: int
    reason: str
    released: bool | None
    type: str = EVENT_REGISTRATION


@dataclass(frozen=True, slots=True)
class WebrtcEvent:
    at: datetime | None
    session_id: str
    call_id: str | None
    state: SessionState
    reason: str
    type: str = EVENT_WEBRTC


@dataclass(frozen=True, slots=True)
class UnknownEvent:
    """An event type the integration does not model yet, carried verbatim."""

    at: datetime | None
    type: str
    raw: Mapping[str, Any]


GatewayEvent = (
    StateEvent | RingEvent | CallEvent | OpenEvent | RegistrationEvent | WebrtcEvent | UnknownEvent
)


def _opt_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _direction(value: Any) -> CallDirection | None:
    return CallDirection(value) if value is not None else None


def _doorphone(value: Any) -> DoorphoneView | None:
    if isinstance(value, Mapping):
        return DoorphoneView.from_dict(value)
    if isinstance(value, str) and value:
        return DoorphoneView(mac=value, name="")
    return None


def parse_event(data: Mapping[str, Any]) -> GatewayEvent:
    """Turn one decoded WebSocket frame into a typed event (DESIGN 5.3)."""
    kind = str(data.get("type", ""))
    if kind == EVENT_STATE:
        return StateEvent(at=parse_at(data), state=StateView.from_dict(data))
    if kind == EVENT_RING:
        return RingEvent(
            at=parse_at(data),
            doorphone=_doorphone(data.get("doorphone")),
            call_id=_opt_str(data.get("call_id")),
        )
    if kind == EVENT_CALL:
        return CallEvent(
            at=parse_at(data),
            call_id=str(data.get("call_id", "")),
            state=CallState(data.get("state", "")),
            direction=_direction(data.get("direction")),
        )
    if kind == EVENT_OPEN:
        return OpenEvent(
            at=parse_at(data),
            actuator=str(data.get("actuator", "")),
            acknowledged=bool(data.get("acknowledged", False)),
            call_id=_opt_str(data.get("call_id")),
        )
    if kind == EVENT_REGISTRATION:
        released = data.get("released")
        return RegistrationEvent(
            at=parse_at(data),
            registered=bool(data.get("registered", False)),
            status_code=int(data.get("status_code", 0)),
            reason=str(data.get("reason", "")),
            released=bool(released) if released is not None else None,
        )
    if kind == EVENT_WEBRTC:
        return WebrtcEvent(
            at=parse_at(data),
            session_id=str(data.get("session_id", "")),
            call_id=_opt_str(data.get("call_id")),
            state=SessionState(data.get("state", "")),
            reason=str(data.get("reason", "")),
        )
    return UnknownEvent(at=parse_at(data), type=kind, raw=data)
