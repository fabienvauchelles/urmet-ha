"""One session per live call: opened, replaced, and closed with the dialog.

Proves the ``MediaSessions`` use case over the ``SessionFactory`` port, with no
aiortc anywhere. An offer opens a session; a second offer on the same call
replaces the first; and the dialog ending closes the session and releases its
tap, so none is left armed on a call that is over.
"""

from __future__ import annotations

import asyncio

import pytest

from urmet_gateway.domain.models import SessionState
from urmet_gateway.usecases.sessions import CALL_ENDED, REPLACED

from .service_graph import open_graph


async def test_session_opens_replaces_and_closes_with_the_call() -> None:
    async with open_graph(with_media=True) as graph:
        assert graph.factory is not None

        call_id = await graph.service.place_call()
        await graph.drain()

        answer = await graph.service.offer("offer-1", call_id)
        await graph.drain()
        assert answer.call_id == call_id
        assert answer.sdp == "answer-to:offer-1"
        first = graph.factory.created[0]
        assert [s.session_id for s in graph.service.state().sessions] == [first.id]
        assert graph.typed("webrtc")[-1].state is SessionState.OPEN

        # A second offer on the same call replaces the first session.
        await graph.service.offer("offer-2", call_id)
        await graph.drain()
        assert len(graph.factory.created) == 2
        assert first.close_reasons == [REPLACED]
        assert len(graph.service.state().sessions) == 1

        # The dialog ends: the session is closed and its tap released, none left.
        handle = graph.transport.invited
        assert handle is not None
        await graph.end_call(handle)
        assert graph.factory.created[1].close_reasons == [CALL_ENDED]
        assert graph.service.state().sessions == []
        assert graph.typed("webrtc")[-1].state is SessionState.CLOSED


async def _let_grace_pass(graph: object) -> None:
    """Give the reap task its grace sleep and let the hangup run to the transport."""
    await graph.settle()  # type: ignore[attr-defined]
    await asyncio.sleep(0.08)
    await graph.settle()  # type: ignore[attr-defined]
    await graph.drain()  # type: ignore[attr-defined]
    await graph.settle()  # type: ignore[attr-defined]


async def test_orphaned_monitor_call_is_hung_up_when_its_viewer_leaves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("urmet_gateway.usecases.sessions.GRACE_S", 0.01)
    async with open_graph(with_media=True) as graph:
        assert graph.factory is not None
        call_id = await graph.service.place_call()
        await graph.drain()
        await graph.service.offer("offer-1", call_id)
        await graph.drain()
        session = graph.factory.created[0]

        # The only viewer leaves: a monitor call the gateway placed must not
        # linger streaming, or the next offer would be mis-bound to it.
        await graph.service.close_session(session.id)
        await _let_grace_pass(graph)

        assert graph.transport.hung_up == [call_id]
        assert graph.service.state().calls == []


async def test_answered_call_survives_its_browser_leg_closing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("urmet_gateway.usecases.sessions.GRACE_S", 0.01)
    async with open_graph(with_media=True) as graph:
        assert graph.factory is not None
        call_id = await graph.ring()
        await graph.service.answer(call_id)
        await graph.drain()
        await graph.service.offer("offer-1", call_id)
        await graph.drain()
        session = graph.factory.created[0]

        # The visitor's dialog is theirs, not the browser's: closing the leg
        # leaves the incoming call up.
        await graph.service.close_session(session.id)
        await _let_grace_pass(graph)

        assert graph.transport.hung_up == []
        assert [c.id for c in graph.service.state().calls] == [call_id]
