"""The eleven request handlers, each a thin translation onto the service.

A handler parses its body, calls one service coroutine, and shapes the answer.
Everything that can fail raises a typed error the middleware turns into a status,
so no handler owns a status table of its own. Body parsing has one rule: an empty
body is an empty object, so an endpoint whose fields all default can be called
with nothing; anything else off-shape is a 400 that names the field.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from aiohttp import web
from pydantic import BaseModel, ValidationError

from urmet_gateway.domain.errors import MalformedBodyError
from urmet_gateway.domain.models import ActuatorName
from urmet_gateway.http.errors import describe_validation
from urmet_gateway.http.models import (
    CallCreated,
    CallRequest,
    DiagnosticsView,
    DirectorFailuresView,
    HealthResponse,
    MicRequest,
    OfferRequest,
)
from urmet_gateway.usecases import DoorphoneService

SettingsEcho = Callable[[], dict[str, object]]
FailureCount = Callable[[], int]


class RestApi:
    """``/api/*`` minus the event stream: health, state, calls, opens, sessions."""

    def __init__(
        self,
        service: DoorphoneService,
        *,
        settings_echo: SettingsEcho = dict,
        failures: FailureCount = lambda: 0,
    ) -> None:
        self._service = service
        self._settings_echo = settings_echo
        self._failures = failures

    def routes(self) -> list[web.RouteDef]:
        """The eleven routes this module owns, in the order of the contract."""
        return [
            web.get("/api/health", self.health),
            web.get("/api/state", self.state),
            web.get("/api/diagnostics", self.diagnostics),
            web.post("/api/call", self.place_call),
            web.post("/api/call/{call_id}/answer", self.answer),
            web.delete("/api/call/{call_id}", self.hang_up),
            web.post("/api/door/open", self.open_door),
            web.post("/api/gate/open", self.open_gate),
            web.post("/api/mic", self.set_mic),
            web.post("/api/webrtc/offer", self.offer),
            web.delete("/api/webrtc/session/{session_id}", self.close_session),
        ]

    async def health(self, _: web.Request) -> web.Response:
        """Answer before the SDK is up, because a supervisor reads a shut port dead."""
        return _json(HealthResponse())

    async def state(self, _: web.Request) -> web.Response:
        """The snapshot the interface draws, read without crossing the worker."""
        return _json(self._service.state())

    async def diagnostics(self, _: web.Request) -> web.Response:
        """The state, the settings echo without secrets, and the silent tally."""
        body = DiagnosticsView(
            state=self._service.state(),
            settings=self._settings_echo(),
            director_failures=DirectorFailuresView(count=self._failures()),
        )
        return _json(body)

    async def place_call(self, request: web.Request) -> web.Response:
        """Place a call, and answer only once it is one you can see and speak into."""
        body = await _parse(request, CallRequest)
        call_id = await self._service.place_call(want_video=body.want_video)
        return _json(CallCreated(call_id=call_id), status=201)

    async def answer(self, request: web.Request) -> web.Response:
        """Answer a ringing dialog and wait until its media streams."""
        await self._service.answer(request.match_info["call_id"])
        return web.Response(status=204)

    async def hang_up(self, request: web.Request) -> web.Response:
        """End a dialog. Idempotent: one already gone is already hung up."""
        await self._service.hangup(request.match_info["call_id"])
        return web.Response(status=204)

    async def open_door(self, request: web.Request) -> web.Response:
        """Drive the pedestrian door, in a named dialog or on a placed one."""
        return await self._open(request, ActuatorName.DOOR)

    async def open_gate(self, request: web.Request) -> web.Response:
        """Drive the sliding gate, one step (open, stop or close)."""
        return await self._open(request, ActuatorName.GATE)

    async def set_mic(self, request: web.Request) -> web.Response:
        """Set whether the doorphone hears this end. The service starts muted."""
        body = await _parse(request, MicRequest)
        await self._service.set_mic_muted(body.muted)
        return web.Response(status=204)

    async def offer(self, request: web.Request) -> web.Response:
        """Bridge a live call into the browser that sent this offer."""
        body = await _parse(request, OfferRequest)
        answer = await self._service.offer(body.sdp, body.call_id)
        return _json(answer, status=201)

    async def close_session(self, request: web.Request) -> web.Response:
        """End one browser leg. Idempotent, like a call ending closes its own."""
        await self._service.close_session(request.match_info["session_id"])
        return web.Response(status=204)

    async def _open(self, request: web.Request, actuator: ActuatorName) -> web.Response:
        await self._service.open(actuator)
        return web.Response(status=204)


def _json(model: BaseModel, *, status: int = 200) -> web.Response:
    """One body, serialised the way the event stream serialises its own."""
    return web.Response(
        text=model.model_dump_json(), status=status, content_type="application/json"
    )


async def _parse[T: BaseModel](request: web.Request, model: type[T]) -> T:
    """Read the body as ``model``. Empty is an empty object; off-shape names the field."""
    raw = await request.read()
    if not raw.strip():
        payload: object = {}
    else:
        try:
            payload = json.loads(raw)
        except ValueError as error:
            raise MalformedBodyError(f"body: not a JSON document ({error})") from error
        if not isinstance(payload, dict):
            raise MalformedBodyError("body: expected a JSON object")
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise MalformedBodyError(describe_validation(error)) from error
