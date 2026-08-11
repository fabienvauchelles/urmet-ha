"""The HTTP surface: the REST API, the event stream, and the application factory.

The outermost layer below the composition root. It imports domain, usecases and
aiohttp, and reaches the SDK, the SIP adapter and the media layer through the use
cases alone. ``create_app`` is what ``main`` hands a wired service and bus to, and
what a test hands the same service built over doubles.
"""

from urmet_gateway.http.app import create_app, utc_now
from urmet_gateway.http.errors import error_middleware
from urmet_gateway.http.models import (
    CallCreated,
    CallRequest,
    DiagnosticsView,
    DirectorFailuresView,
    HealthResponse,
    MicRequest,
    OfferRequest,
)
from urmet_gateway.http.rest import RestApi
from urmet_gateway.http.ws import EventsApi

__all__ = [
    "CallCreated",
    "CallRequest",
    "DiagnosticsView",
    "DirectorFailuresView",
    "EventsApi",
    "HealthResponse",
    "MicRequest",
    "OfferRequest",
    "RestApi",
    "create_app",
    "error_middleware",
    "utc_now",
]
