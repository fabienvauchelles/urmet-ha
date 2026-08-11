"""Boot and shutdown, in the one order the native stack tolerates.

The registration supervisor owns the binding; the service owns the calls, the
media and the event stream; the worker owns the single SDK thread. Bringing them
up is one call (the supervisor registers in the background so the health port
answers at once). Bringing them down is an order that is not negotiable, because
nothing native may outlive the stack: the browser legs are closed before the
client is stopped, and the bus stays open until the last registration event has
been published, so a listener still learns the door went down.

This runtime is the composition root's, and the test composition roots reuse it,
so the shutdown order lives in exactly one place and cannot drift between them.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from urmet_gateway.domain.models import RegistrationEvent
from urmet_gateway.sip.supervision import RegistrationOutcome, RegistrationSupervisor
from urmet_gateway.sip.worker import SdkWorker
from urmet_gateway.usecases import DoorphoneService, EventBus


def registration_publisher(
    *,
    bus: EventBus,
    service: DoorphoneService,
    clock: Callable[[], datetime],
) -> Callable[[RegistrationOutcome], None]:
    """Adapt the supervisor's outcome onto the bus, then the state that follows it.

    The supervisor reports a plain outcome; the wire wants a ``registration``
    event followed by a ``state`` event, because a subscriber's view must never
    disagree with the last event it saw. ``released`` is only meaningful on a
    release attempt, so ``None`` reads as the steady-state ``True``.
    """

    def publish(outcome: RegistrationOutcome) -> None:
        bus.publish(
            RegistrationEvent(
                at=clock(),
                registered=outcome.registered,
                status_code=outcome.status_code,
                reason=outcome.reason,
                released=True if outcome.released is None else outcome.released,
            )
        )
        service.publish_state()

    return publish


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
