"""SIP adapters: the two thread crossings between the SDK and the event loop.

``SdkWorker`` is the one thread every blocking SDK call goes out on.
``CallbackBridge`` is the one hop every SIP callback comes back on. ``WorkerTap``
is a call's media tap with the handle bound and the thread hop made.
``RegistrationSupervisor``
keeps the binding alive and reports honestly when it cannot, ``ClientHolder`` is
the indirection the command path resolves the current client through, and
``GatewayRuntime`` boots the supervisor and tears the stack down in one order.
"""

from urmet_gateway.sip.bridge import (
    CallbackBridge,
    CallStateHandler,
    DoorbellSource,
    RingHandler,
)
from urmet_gateway.sip.holder import ClientHolder, NoClientError, rebuilding_factory
from urmet_gateway.sip.lifecycle import GatewayRuntime, registration_publisher
from urmet_gateway.sip.supervision import (
    LIVENESS_INTERVAL_S,
    ClientFactory,
    OnConnected,
    RegistrationOutcome,
    RegistrationSupervisor,
    SupervisedClient,
)
from urmet_gateway.sip.tap import MAX_TAP_BYTES, WorkerTap
from urmet_gateway.sip.worker import SdkWorker, WorkerStoppedError

__all__ = [
    "LIVENESS_INTERVAL_S",
    "MAX_TAP_BYTES",
    "CallStateHandler",
    "CallbackBridge",
    "ClientFactory",
    "ClientHolder",
    "DoorbellSource",
    "GatewayRuntime",
    "NoClientError",
    "OnConnected",
    "RegistrationOutcome",
    "RegistrationSupervisor",
    "RingHandler",
    "SdkWorker",
    "SupervisedClient",
    "WorkerStoppedError",
    "WorkerTap",
    "rebuilding_factory",
    "registration_publisher",
]
