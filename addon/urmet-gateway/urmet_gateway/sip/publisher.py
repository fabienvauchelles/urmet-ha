"""The supervisor's outcome, adapted onto the event bus.

The supervisor reports a plain ``RegistrationOutcome``; the wire wants a
``registration`` event followed by a ``state`` event. Keeping that translation
here is what lets the supervisor stay ignorant of the wire and the use cases stay
ignorant of the binding.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from urmet_gateway.domain.models import RegistrationEvent
from urmet_gateway.sip.supervision import RegistrationOutcome
from urmet_gateway.usecases import DoorphoneService, EventBus


def registration_publisher(
    *,
    bus: EventBus,
    service: DoorphoneService,
    clock: Callable[[], datetime],
) -> Callable[[RegistrationOutcome], None]:
    """Adapt the supervisor's outcome onto the bus, then the state that follows it.

    A ``registration`` event is always followed by a ``state`` event, because a
    subscriber's view must never disagree with the last event it saw.
    ``released`` is only meaningful on a release attempt, so ``None`` reads as
    the steady-state ``True``.
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
