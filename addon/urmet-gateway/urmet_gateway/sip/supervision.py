"""Keeping the SIP binding alive, and reporting honestly when it is not.

The SDK registers once and retries nothing: no reconnection, no refresh on
expiry, no backoff, and no callback to observe a binding that quietly died. It
also makes ``stop()`` terminal, so recovery is not a re-register but a fresh
client over a fresh transport. All of that is this supervisor's, and nothing
else builds a client after the first one.

It runs as a background task started at boot and never awaited, so the health
port answers before the registrar has. On a refused or lost binding it reconnects
with the measured cadence 5, 10, 20, 40, 60 s, the last value repeating. A retry
that would only queue behind a user command is deferred at the same delay and the
backoff does not advance, because nothing was tried. It never replays a command,
only the connection. And a release it could not confirm is published as such, so
the integration can turn a leaked binding into a repair rather than a silence.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Final, Protocol

from urmet_sdk import NotRegisteredError, UrmetError

from urmet_gateway.sip.worker import SdkWorker

logger = logging.getLogger(__name__)

# Reconnect cadence, measured against the vendor cloud. The last value repeats.
_BACKOFF_S: Final[tuple[float, ...]] = (5.0, 10.0, 20.0, 40.0, 60.0)
# An explicit liveness re-REGISTER, because keepalive does not reach a TLS
# transport and no Flow-Timer was ever observed. Well inside the 900 s expiry.
LIVENESS_INTERVAL_S: Final = 300.0

RELEASED_REASON: Final = "binding released"
NOT_RELEASED_REASON: Final = "the registrar still holds the binding; it will expire"

Sleep = Callable[[float], Awaitable[None]]
OnConnected = Callable[[], Awaitable[None]]


async def _noop_on_connected() -> None:
    """The default post-connect hook: a fresh binding needs nothing done to it."""


@dataclass(frozen=True, slots=True)
class RegistrationOutcome:
    """What the supervisor publishes about the binding, straight to the loop.

    ``released`` is None except on a release attempt: True when the registrar
    took the binding back, False when it could not be confirmed and the door may
    be degraded until the binding expires.
    """

    registered: bool
    status_code: int
    reason: str
    released: bool | None = None


class SupervisedClient(Protocol):
    """The subset of the SDK client the supervisor drives and reads.

    ``UrmetClient`` satisfies it structurally, so the supervisor names an
    abstraction and the composition root injects the concrete transport.
    """

    def start(self, *, timeout: float | None = None) -> None: ...
    def stop(self) -> bool: ...
    @property
    def registered(self) -> bool: ...
    @property
    def registration_status_code(self) -> int: ...
    @property
    def registration_reason(self) -> str: ...


ClientFactory = Callable[[], SupervisedClient]


class RegistrationSupervisor:
    """Registers, refreshes, reconnects, and reports the binding's true state."""

    def __init__(
        self,
        *,
        build_client: ClientFactory,
        worker: SdkWorker,
        publish: Callable[[RegistrationOutcome], None],
        sleep: Sleep = asyncio.sleep,
        is_busy: Callable[[], bool] | None = None,
        on_connected: OnConnected = _noop_on_connected,
        register_timeout_s: float | None = None,
        liveness_interval_s: float = LIVENESS_INTERVAL_S,
    ) -> None:
        self._build_client = build_client
        self._worker = worker
        self._publish = publish
        self._sleep = sleep
        self._is_busy = is_busy if is_busy is not None else (lambda: False)
        self._on_connected = on_connected
        self._register_timeout_s = register_timeout_s
        self._liveness_interval_s = liveness_interval_s
        self._step = 0
        self._stopped = False
        self._task: asyncio.Task[None] | None = None
        self._client: SupervisedClient | None = None

    async def start(self) -> None:
        """Launch the supervise loop and return at once, never awaiting it."""
        if self._task is not None:
            return
        self._task = asyncio.get_running_loop().create_task(self._supervise())
        self._task.add_done_callback(self._log_if_died)

    def _log_if_died(self, task: asyncio.Task[None]) -> None:
        """A supervise loop that ends by raising must never do so silently."""
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("registration supervisor stopped on an unhandled error", exc_info=error)

    async def stop(self) -> None:
        """End the loop and release the binding, reporting a release it could not get.

        Terminal. The loop is cancelled first so no reconnect races the release,
        then the live client is stopped on the worker thread and the outcome, an
        obtained release or an unconfirmed one, is published a last time.
        """
        if self._stopped:
            return
        self._stopped = True
        task = self._task
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        client = self._client
        self._client = None
        if client is not None:
            await self._release(client)

    # -- the loop ---------------------------------------------------------

    async def _supervise(self) -> None:
        """Build a client, register it, hold the binding, reconnect on loss."""
        while not self._stopped:
            client = self._build_client()
            self._client = client
            logger.info("registering with the Urmet cloud")
            try:
                await self._worker.run(client.start, timeout=self._register_timeout_s)
            except UrmetError as error:
                logger.warning("registration refused: %s", error)
                self._publish_down(client, reason=str(error))
                await self._release(client)
                await self._wait_before_retry()
                continue
            except Exception as error:
                logger.exception("registration attempt raised, will retry")
                self._publish_down(client, reason=str(error))
                await self._release(client)
                await self._wait_before_retry()
                continue
            logger.info("registered with the Urmet cloud")
            self._publish_up(client)
            self._reset_backoff()
            # A fresh client is what the rest of the graph now speaks through, and
            # it comes up with the microphone open by default. The post-connect
            # hook realigns that owned state onto the new client, so a reconnect
            # can never open the panel's near end behind the owner's back.
            await self._on_connected()
            try:
                await self._hold(client)
            except UrmetError as error:
                logger.warning("binding lost: %s", error)
                self._publish_down(client, reason=str(error))
            except Exception as error:
                logger.exception("hold loop raised, will reconnect")
                self._publish_down(client, reason=str(error))
            await self._release(client)
            await self._wait_before_retry()

    async def _hold(self, client: SupervisedClient) -> None:
        """Refresh the binding on the liveness cadence until one refresh fails.

        A failed refresh raises out of here and the loop reconnects with a fresh
        client, never a replayed command. ``start`` is idempotent while the
        binding is live, so re-registering it is the whole of the refresh.
        """
        while not self._stopped:
            await self._sleep(self._liveness_interval_s)
            if self._stopped:
                return
            await self._worker.run(client.start, timeout=self._register_timeout_s)
            if not client.registered:
                raise NotRegisteredError("liveness re-REGISTER did not confirm the binding")
            self._publish_up(client)

    async def _wait_before_retry(self) -> None:
        """Wait the current backoff, deferring at the same delay while busy.

        The delay advances only when a real attempt is about to be made. A retry
        deferred because the worker is busy waits the same delay again and the
        backoff stays where it is, because nothing was tried.
        """
        delay = self._current_delay()
        await self._sleep(delay)
        while not self._stopped and self._is_busy():
            await self._sleep(delay)
        self._advance()

    async def _release(self, client: SupervisedClient) -> None:
        """Stop the client and publish whether the registrar took the binding."""
        try:
            released = await self._worker.run(client.stop)
        except UrmetError as error:
            logger.warning("release raised: %s", error)
            released = False
        reason = RELEASED_REASON if released else NOT_RELEASED_REASON
        self._publish(
            RegistrationOutcome(registered=False, status_code=0, reason=reason, released=released)
        )

    # -- backoff ----------------------------------------------------------

    def _current_delay(self) -> float:
        return _BACKOFF_S[min(self._step, len(_BACKOFF_S) - 1)]

    def _advance(self) -> None:
        self._step += 1

    def _reset_backoff(self) -> None:
        self._step = 0

    # -- publishing -------------------------------------------------------

    def _publish_up(self, client: SupervisedClient) -> None:
        self._publish(
            RegistrationOutcome(
                registered=True,
                status_code=client.registration_status_code,
                reason=client.registration_reason,
            )
        )

    def _publish_down(self, client: SupervisedClient, *, reason: str) -> None:
        self._publish(
            RegistrationOutcome(
                registered=False,
                status_code=client.registration_status_code,
                reason=reason,
            )
        )
