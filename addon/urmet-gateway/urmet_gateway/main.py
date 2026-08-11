"""The composition root: settings, the real SDK client, the supervisor, the app.

The only module that names the production boundaries. It builds the cloud plane
and the pjsua2 transport, hands them to ``UrmetClient``, and forces
``null_sound_device`` on as a literal so no variable can open the server's own
microphone onto the street panel. pjsua2 itself is never imported here:
``PjsipTransport`` loads the native binding on its own, on the first register.

Registration is not owned here either. The ``RegistrationSupervisor`` owns the
binding's whole lifecycle: it builds each client through the factory below, binds
the callback bridge to it, updates the holder every command resolves through, and
reconnects with backoff on a lost binding. The service drives calls and media over
whatever client the holder currently points at. Shutdown is aiohttp's and
graceful: a signal ends ``run_app``, whose cleanup awaits ``GatewayRuntime.shutdown``,
which closes the browser legs, releases the binding and joins the SDK thread in
the one order the native stack tolerates.

The WebRTC media leg is composed here through ``MediaSessionFactory``: each browser
offer is answered with a ``MediaSession`` over a fresh aiortc peer connection wired
to a ``WorkerTap`` on the current transport. The transport is the ``MediaTap`` this
module hands the tap holder on every build, so a reconnect that rebuilds it whole is
picked up by the next session, and no session ever names a call that is not its own.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from aiohttp import web
from pydantic import ValidationError
from urmet_sdk import (
    Actuator,
    CallHandle,
    CloudClient,
    Doorphone,
    MediaTap,
    PjsipTransport,
    Settings,
    UrmetClient,
)
from urmet_sdk.sip.pjsip_binding import director_failures

from urmet_gateway.http import create_app, utc_now
from urmet_gateway.media_factory import MediaSessionFactory
from urmet_gateway.settings import GatewaySettings
from urmet_gateway.sip import (
    CallbackBridge,
    ClientHolder,
    GatewayRuntime,
    RegistrationSupervisor,
    SdkWorker,
    rebuilding_factory,
    registration_publisher,
)
from urmet_gateway.usecases import DoorphoneService, EventBus

logger = logging.getLogger("urmet_gateway")

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
EXIT_CONFIG = 2
DIAG_DIR = Path(__file__).resolve().parent / "diag"

# Which environment variables a settings model was populated from, so a failure
# names what the owner has to write rather than the field pydantic saw.
PREFIXES = {"GatewaySettings": "URMET_GW_", "Settings": "URMET_"}

ClientProvider = Callable[[], UrmetClient]


class ConfigurationError(ValueError):
    """A setting the gateway cannot start without is missing or unusable."""


class SdkDoorphonePort:
    """A ``DoorphonePort`` over whatever client the holder currently points at.

    It owns no client and no lifecycle: the supervisor builds, registers and
    rebuilds; this port only drives commands. Every command resolves the current
    client through the provider before crossing the single worker thread, so a
    rebuild that happened while the binding was down is picked up transparently,
    and a command in flight can never race one (the worker being busy defers the
    supervisor's reconnect).
    """

    def __init__(self, *, provider: ClientProvider, worker: SdkWorker) -> None:
        self._provider = provider
        self._worker = worker

    @property
    def registered(self) -> bool:
        return self._provider().registered

    def known_doorphone(self) -> Doorphone | None:
        return self._provider().known_doorphone()

    async def view_door(self, *, want_video: bool) -> CallHandle:
        return await self._worker.run(self._provider().view_door, want_video=want_video)

    async def answer(self, call: CallHandle) -> None:
        await self._worker.run(self._provider().answer, call)

    async def hangup(self, call: CallHandle) -> None:
        await self._worker.run(self._provider().hangup, call)

    async def open_during(self, call: CallHandle, actuator: Actuator) -> None:
        await self._worker.run(self._provider().open_during, call, actuator)

    async def open_on_demand(self, actuator: Actuator) -> None:
        client = self._provider()
        command = client.open_door if actuator is Actuator.DOOR else client.open_gate
        await self._worker.run(command)

    async def set_mic_muted(self, muted: bool) -> None:
        await self._worker.run(self._provider().set_mic_muted, muted)


def force_null_sound_device(settings: Settings) -> Settings:
    """Return the SDK settings with the null sound device forced on.

    Left to itself the SDK opens this machine's ALSA capture device and wires it
    into every call, so the room around the server is what the street panel hears
    (measured outgoing level 0.42 with nobody speaking). Forcing it here rather
    than offering a switch is what keeps a wrong ``.env`` from being a privacy leak.
    """
    return settings.model_copy(update={"null_sound_device": True})


def load_settings() -> tuple[GatewaySettings, Settings]:
    """The gateway settings and the SDK's, or an error naming the variables."""
    try:
        gateway = GatewaySettings()
        sdk_settings = Settings()
    except ValidationError as error:
        raise ConfigurationError(_variables(error)) from error
    return gateway, force_null_sound_device(sdk_settings)


async def build_app(gateway: GatewaySettings, sdk_settings: Settings) -> web.Application:
    """Wire the production stack on the loop that will serve it.

    Awaited by ``run_app`` inside the loop, because the bus, the service and the
    bridge all capture the running loop when they are built. The transport is handed
    to the tap holder on every build as a ``MediaTap``, and the session factory
    resolves the current one for every browser offer.
    """
    loop = asyncio.get_running_loop()
    worker = SdkWorker()
    holder: ClientHolder[UrmetClient] = ClientHolder()
    tap_holder: ClientHolder[MediaTap] = ClientHolder()
    bus = EventBus()
    port = SdkDoorphonePort(provider=holder.current, worker=worker)
    factory = MediaSessionFactory(
        tap=tap_holder.current, worker=worker, video_settle_s=gateway.video_settle_s
    )
    service = DoorphoneService(port=port, bus=bus, clock=utc_now, factory=factory)
    bridge = CallbackBridge(
        loop=loop, on_ring=service.ring_arrived, on_call=service.call_state_arrived
    )

    def build_client() -> UrmetClient:
        transport = PjsipTransport(sdk_settings)
        cloud = CloudClient(sdk_settings.cloud_base_url, timeout_s=sdk_settings.http_timeout_s)
        client = UrmetClient(sdk_settings, cloud=cloud, transport=transport)
        bridge.bind(client)
        holder.set(client)
        tap_holder.set(transport)
        return client

    supervisor = RegistrationSupervisor(
        build_client=rebuilding_factory(build_client),
        worker=worker,
        publish=registration_publisher(bus=bus, service=service, clock=utc_now),
        is_busy=lambda: worker.busy,
        on_connected=service.realign,
    )
    runtime = GatewayRuntime(bus=bus, worker=worker, supervisor=supervisor, service=service)
    return create_app(
        service=service,
        bus=bus,
        clock=utc_now,
        settings_echo=lambda: _settings_echo(gateway, sdk_settings),
        failures=lambda: director_failures.count,
        diag_dir=DIAG_DIR,
        on_startup=runtime.start,
        on_cleanup=runtime.shutdown,
    )


def main() -> int:
    """Serve until a signal ends it. Returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    try:
        gateway, sdk_settings = load_settings()
    except ConfigurationError as error:
        logger.error("%s", error)
        return EXIT_CONFIG
    level = gateway.log_level.upper()
    # Set the root logger too, not just ours, so the SDK and its pjsip layer
    # surface their own login and REGISTER lines at debug, which is what a remote
    # operator needs to see why a binding did or did not come up.
    logging.getLogger().setLevel(level)
    logger.setLevel(level)
    web.run_app(build_app(gateway, sdk_settings), host=gateway.host, port=gateway.port)
    return 0


def _settings_echo(gateway: GatewaySettings, sdk_settings: Settings) -> dict[str, object]:
    """The settings a diagnostics reader may see, with every secret left out."""
    echo: dict[str, object] = dict(gateway.model_dump())
    echo.update(
        sip_realm=sdk_settings.sip_realm,
        doorphone_mac=sdk_settings.doorphone_mac,
        doorphone_name=sdk_settings.doorphone_name,
        register_expiry_s=sdk_settings.register_expiry_s,
        null_sound_device=sdk_settings.null_sound_device,
    )
    return echo


def _variables(error: ValidationError) -> str:
    """The environment variables behind the offending fields, never their values."""
    prefix = PREFIXES.get(error.title, "URMET_")
    fields = sorted({str(item["loc"][0]) for item in error.errors() if item["loc"]})
    named = ", ".join(f"{prefix}{field.upper()}" for field in fields) or "unknown setting"
    return f"incomplete configuration: {named}"


if __name__ == "__main__":
    raise SystemExit(main())
