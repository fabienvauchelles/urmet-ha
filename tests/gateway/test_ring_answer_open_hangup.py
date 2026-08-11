"""The path the gateway exists for: the panel rings, someone answers, opens, hangs up.

This decides the threading and the event ordering. The doorbell arrives on the
SDK worker thread, is marshalled onto the loop by the port, and reaches a
subscriber as an event; RINGING is published from the inbound edge, before the
180 and before anything that can fail. Every non-state event is followed by a
state event, so a subscriber's view can never disagree with what it just saw.
"""

from __future__ import annotations

from typing import Any

from urmet_sdk import Actuator, CallState

from urmet_gateway.domain.models import ActuatorName, Direction, EventType

from .service_graph import DOORPHONE_MAC, open_graph


def _state_follows_every_event(events: list[Any]) -> None:
    """Every non-state event is immediately followed by a state event."""
    assert events, "nothing was published"
    for index, event in enumerate(events):
        if event.type is EventType.STATE:
            continue
        assert index + 1 < len(events), "an event was not followed by a state"
        assert events[index + 1].type is EventType.STATE
    assert events[-1].type is EventType.STATE


async def test_ring_answer_open_hangup() -> None:
    async with open_graph() as graph:
        call_id = await graph.ring()

        rings = graph.typed("ring")
        assert len(rings) == 1
        assert rings[0].doorphone.mac == DOORPHONE_MAC
        assert rings[0].call_id == call_id

        # RINGING is reported from the inbound edge, and as an inbound dialog.
        ringing = [e for e in graph.typed("call") if e.state is CallState.RINGING]
        assert ringing and ringing[0].direction is Direction.INCOMING

        await graph.service.answer(call_id)
        await graph.drain()
        assert graph.transport.answered == [call_id]
        streaming = [e for e in graph.typed("call") if e.state is CallState.STREAMING]
        assert streaming and streaming[0].direction is Direction.INCOMING
        calls = graph.service.state().calls
        assert [(c.id, c.state, c.direction) for c in calls] == [
            (call_id, CallState.STREAMING, Direction.INCOMING)
        ]

        # The open travels inside the answered dialog and the panel acknowledges it.
        await graph.service.open(ActuatorName.DOOR, call_id)
        await graph.drain()
        opens = graph.typed("open")
        assert len(opens) == 1
        assert opens[0].actuator is ActuatorName.DOOR
        assert opens[0].acknowledged is True
        assert len(graph.transport.opens) == 1
        assert graph.transport.opens[0].call_id == call_id
        assert graph.transport.opens[0].actuator is Actuator.DOOR

        await graph.service.hangup(call_id)
        await graph.drain()
        assert graph.transport.hung_up == [call_id]
        assert [e for e in graph.typed("call") if e.state is CallState.ENDED]
        assert graph.service.state().calls == []

        _state_follows_every_event(graph.events())
