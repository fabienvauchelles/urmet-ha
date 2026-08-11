"""One session per live call: opened, replaced, and closed with the dialog.

Proves the ``MediaSessions`` use case over the ``SessionFactory`` port, with no
aiortc anywhere. An offer opens a session; a second offer on the same call
replaces the first; and the dialog ending closes the session and releases its
tap, so none is left armed on a call that is over.
"""

from __future__ import annotations

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
