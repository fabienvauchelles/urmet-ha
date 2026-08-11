"""The aiohttp application: the API, the event stream, the diagnostics page.

Everything it needs is handed to it. It builds no client, no bus and no service,
which is what lets a test drive the same application over doubles, and it never
names the SIP layer: startup and shutdown are two opaque coroutines the
composition root hands in. Startup returns at once (the supervisor registers in
the background) so ``/api/health`` answers before the SDK is up. Shutdown is
awaited in ``on_cleanup``, so the calls are hung up and the binding released
before the process is allowed to exit.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import web
from aiohttp.typedefs import Handler

from urmet_gateway.http.errors import error_middleware
from urmet_gateway.http.rest import FailureCount, RestApi, SettingsEcho
from urmet_gateway.http.ws import EventsApi
from urmet_gateway.usecases import DoorphoneService, EventBus

logger = logging.getLogger(__name__)

INDEX_FILE = "index.html"
LifecycleHook = Callable[[], Awaitable[None]]


def utc_now() -> datetime:
    """The wall clock the composition root stamps its events with, UTC."""
    return datetime.now(UTC)


class Lifecycle:
    """Runs the composition root's boot behind the open port, and its teardown before exit."""

    def __init__(
        self, *, on_startup: LifecycleHook | None, on_cleanup: LifecycleHook | None
    ) -> None:
        self._on_startup = on_startup
        self._on_cleanup = on_cleanup

    async def on_startup(self, _: web.Application) -> None:
        """Kick boot off, which returns at once so the port opens straight away."""
        if self._on_startup is None:
            return
        try:
            await self._on_startup()
        except Exception:
            logger.exception("boot failed; the doorbell will not be heard")

    async def on_cleanup(self, _: web.Application) -> None:
        """Hang up, un-REGISTER, and join the SDK thread before the process exits."""
        if self._on_cleanup is None:
            return
        await self._on_cleanup()


def create_app(
    *,
    service: DoorphoneService,
    bus: EventBus,
    clock: Callable[[], datetime] = utc_now,
    settings_echo: SettingsEcho = dict,
    failures: FailureCount = lambda: 0,
    diag_dir: Path | None = None,
    on_startup: LifecycleHook | None = None,
    on_cleanup: LifecycleHook | None = None,
) -> web.Application:
    """Assemble the surface: REST, the event stream, the diagnostics page, the lifecycle.

    ``clock`` is the one the service was built with, so the snapshot a new
    subscriber receives is stamped by the same clock as the events that follow.
    ``diag_dir`` is where the ingress diagnostics page lives; None serves no page.
    ``on_startup`` and ``on_cleanup`` are the composition root's boot and teardown;
    the http layer names neither the supervisor nor the worker they drive.
    """
    app = web.Application(middlewares=[error_middleware])
    app.add_routes(RestApi(service, settings_echo=settings_echo, failures=failures).routes())
    app.add_routes(EventsApi(service, bus, clock=clock).routes())
    _serve_diagnostics_page(app, diag_dir)
    lifecycle = Lifecycle(on_startup=on_startup, on_cleanup=on_cleanup)
    app.on_startup.append(lifecycle.on_startup)
    app.on_cleanup.append(lifecycle.on_cleanup)
    return app


def _serve_diagnostics_page(app: web.Application, diag_dir: Path | None) -> None:
    """Serve the ingress panel from ``diag_dir``, under the API rather than over it.

    The static route claims the whole of ``/`` and still cannot shadow the API:
    aiohttp resolves the most explicit path first, so ``/api/state`` is matched by
    its own route whatever order the two were added in.
    """
    if diag_dir is None:
        return
    root = diag_dir.expanduser()
    app.router.add_get("/", _index(root))
    if not root.is_dir():
        logger.warning("no diagnostics page under %s", root)
        return
    app.router.add_static("/", root)


def _index(root: Path) -> Handler:
    """The panel itself, the one route the diagnostics page needs by name."""

    async def index(_: web.Request) -> web.StreamResponse:
        page = root / INDEX_FILE
        if not page.is_file():
            raise web.HTTPNotFound(text=f"no {INDEX_FILE} under {root}", content_type="text/plain")
        return web.FileResponse(page)

    return index
