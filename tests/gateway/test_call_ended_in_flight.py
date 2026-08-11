"""The dialog ends while the command that placed it is still in flight.

The visitor walks away between the panel starting its media and the SDK handing
the call back. The transport reports the end, the service forgets the dialog, and
the command then returns holding a handle to something already over. It must not
write that handle down again: no further callback carries that id, so the entry
would never leave and the doorphone would look busy until a restart. Only the
transport says a dialog exists; a command may refine an entry, never create one.
"""

from __future__ import annotations

import asyncio

from urmet_sdk import CallState

from urmet_gateway.domain.models import Direction

from .service_graph import open_graph


async def test_call_ended_in_flight() -> None:
    async with open_graph() as graph:
        graph.transport.hold_invite()
        placing = asyncio.create_task(graph.service.place_call(want_video=True))

        call = await graph.reach_invite()
        # The panel streamed, so the service is watching a live outgoing dialog,
        # and the command is still sitting in the transport with the handle.
        await graph.drain()
        assert [(c.id, c.state, c.direction) for c in graph.service.state().calls] == [
            (call.id, CallState.STREAMING, Direction.OUTGOING)
        ]

        await graph.end_call(call)
        graph.transport.release_invite()

        returned = await placing
        assert returned == call.id

        # The command did not resurrect the dialog: nothing is up.
        assert graph.service.state().calls == []

        # And the doorphone is free: the next call is placed and shown as usual.
        second = await graph.service.place_call()
        await graph.drain()
        assert second != call.id
        assert [c.id for c in graph.service.state().calls] == [second]
