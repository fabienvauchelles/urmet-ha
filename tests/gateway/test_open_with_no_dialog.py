"""An open with no live call: the SDK places a dialog, opens, and releases it.

This is the panel's auto-insertion. With no call id the SDK invites the panel
without video, sends the INFO, and hangs the dialog up in a finally, so an open
from an automation that needs no picture leaves nothing standing.
"""

from __future__ import annotations

from urmet_sdk import Actuator

from urmet_gateway.domain.models import ActuatorName

from .service_graph import open_graph


async def test_open_with_no_dialog() -> None:
    async with open_graph() as graph:
        await graph.service.open(ActuatorName.DOOR)
        await graph.drain()

        # A call was placed without video to carry the INFO.
        assert len(graph.transport.invites) == 1
        placed = graph.transport.invites[0]
        assert placed.want_video is False

        # The INFO went out once, acknowledged.
        assert len(graph.transport.opens) == 1
        assert graph.transport.opens[0].actuator is Actuator.DOOR
        opens = graph.typed("open")
        assert opens[-1].actuator is ActuatorName.DOOR
        assert opens[-1].acknowledged is True

        # The dialog the SDK opened for the command was released again.
        assert graph.transport.hung_up == [placed.call_id]
        assert graph.service.state().calls == []
