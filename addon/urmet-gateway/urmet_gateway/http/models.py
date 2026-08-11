"""The request and response bodies of the HTTP surface, off-shape rejected.

Every request model forbids an unknown field, so a caller that sent the wrong
shape is told which field rather than having it silently defaulted. The responses
reuse the domain vocabulary where it already says the right thing: a state read is
a ``StateView``, an answered offer is a ``SessionAnswer``. Only the small bodies
this layer alone speaks live here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from urmet_gateway.domain.models import StateView


class _Body(BaseModel):
    """A request body that refuses any field the endpoint does not document."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    """The one thing ``GET /api/health`` says, without touching the SDK."""

    ok: bool = True


class CallRequest(_Body):
    """``POST /api/call``: place an on-demand call, with video unless refused."""

    want_video: bool = True


class CallCreated(BaseModel):
    """``201`` from ``POST /api/call``: an id for a call already streaming."""

    call_id: str


class OpenRequest(_Body):
    """``POST /api/door|gate/open``: drive an actuator, in a dialog or on its own.

    ``call_id`` null places and releases a short audio-only call for the INFO; a
    ring in progress is answered first and the INFO goes into that dialog.
    """

    call_id: str | None = None


class MicRequest(_Body):
    """``POST /api/mic``: whether the doorphone may hear this end at all."""

    muted: bool


class OfferRequest(_Body):
    """``POST /api/webrtc/offer``: the browser's own offer, for one live call.

    ``call_id`` null takes the newest streaming call. ``type`` is the browser's
    own ``offer`` and is carried for symmetry with the answer, never acted on.
    """

    sdp: str
    type: Literal["offer"] = "offer"
    call_id: str | None = None


class DirectorFailuresView(BaseModel):
    """How many SWIG directors failed in silence, the only sign a media path is."""

    count: int = 0


class DiagnosticsView(BaseModel):
    """``GET /api/diagnostics``: the state, the settings echo, the silent tally.

    The settings echo carries no credential: the cloud password never leaves the
    add-on and is not echoed, so there is nothing to redact but tidiness.
    """

    state: StateView
    settings: dict[str, object]
    director_failures: DirectorFailuresView
