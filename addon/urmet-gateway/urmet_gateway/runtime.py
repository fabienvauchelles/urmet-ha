"""Boot and shutdown, in the one order the native stack tolerates.

This is composition, not a SIP adapter: it holds the supervisor, the service, the
bus and the worker together and decides the order they come up and go down in. It
sits beside ``main.py`` and ``media_factory.py`` for that reason, and the test
composition roots reuse it, so the shutdown order lives in exactly one place and
cannot drift between them.

The registration supervisor owns the binding; the service owns the calls, the
media and the event stream; the worker owns the single SDK thread. Bringing them
up is one call (the supervisor registers in the background so the health port
answers at once). Bringing them down is an order that is not negotiable, because
nothing native may outlive the stack: the browser legs are closed before the
client is stopped, and the bus stays open until the last registration event has
been published, so a listener still learns the door went down.
"""

from __future__ import annotations

from urmet_gateway.sip import RegistrationSupervisor, SdkWorker
from urmet_gateway.usecases import DoorphoneService, EventBus


class GatewayRuntime:
    """Starts the supervisor at boot and tears the whole stack down in order."""

    def __init__(
        self,
        *,
        bus: EventBus,
        worker: SdkWorker,
        supervisor: RegistrationSupervisor,
        service: DoorphoneService,
    ) -> None:
        self._bus = bus
        self._worker = worker
        self._supervisor = supervisor
        self._service = service

    async def start(self) -> None:
        """Launch registration in the background and return at once."""
        await self._supervisor.start()

    async def shutdown(self) -> None:
        """Close legs, release the binding, drain state, then join the thread.

        The order is DESIGN 5.5: sessions first so no tap is armed on a call when
        the stack comes down, the supervisor's release next (it stops the client
        and publishes the registration outcome), the calls cleared and the final
        state drained, the bus closed so that last event still landed, and the
        worker joined last so the release ran on a thread that was still alive.
        """
        await self._service.close_sessions()
        await self._supervisor.stop()
        self._service.clear_calls()
        self._service.publish_state()
        self._bus.close()
        await self._worker.aclose()
