"""An open the panel never acknowledged: unknown, never failed, and never retried.

The INFO left and nothing came back, so the door state is unknown. The only
honest event is ``acknowledged: false``, and the only dangerous act is a retry:
on a step-by-step gate a second pulse is a reversal, so the gateway never issues
one. The dialog opened to carry the command is still released.
"""

from __future__ import annotations

import pytest

from urmet_gateway.domain.errors import OpenNotAcknowledgedError
from urmet_gateway.domain.models import ActuatorName

from .service_graph import open_graph


async def test_open_unacknowledged() -> None:
    async with open_graph(open_acknowledged=False) as graph:
        with pytest.raises(OpenNotAcknowledgedError):
            await graph.service.open(ActuatorName.DOOR)
        await graph.drain()

        opens = graph.typed("open")
        assert len(opens) == 1
        assert opens[0].actuator is ActuatorName.DOOR
        assert opens[0].acknowledged is False

        # No retry: exactly one INFO and one placed dialog, and it was released.
        assert len(graph.transport.opens) == 1
        assert len(graph.transport.invites) == 1
        assert graph.transport.hung_up == [graph.transport.invites[0].call_id]
        assert graph.service.state().calls == []
