"""What to do about a media path that has stopped moving.

A stalled reader here is a stopped doorphone: the recorder writes from pjmedia's
clock thread, which drives every call's bridge, so a pipe nobody drains blocks the
conversation, and noticing is not enough. Two failures, one shape: a stalled reader
is silence, a dead encoder a probe. Two budgets (trap 13), because the first byte
lands ~10 s after arming, too late for one tight enough to catch a stall.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Half a frame interval, so a dead encoder is noticed at once and the loop is not.
DEFAULT_POLL_S = 0.5


@dataclass(frozen=True)
class Stall:
    """Why a watchdog fired, and how long the silence had lasted."""

    name: str
    reason: str
    silent_for_s: float


class Watchdog:
    """Watches something that must keep moving, and reacts once when it stops.

    ``beat`` is two float stores and no lock, callable from the clock thread that
    must never be delayed; everything else runs on the loop.
    """

    def __init__(
        self,
        *,
        name: str,
        timeout_s: float,
        on_stall: Callable[[Stall], Awaitable[None]],
        startup_timeout_s: float | None = None,
        probe: Callable[[], str | None] | None = None,
        poll_s: float = DEFAULT_POLL_S,
    ) -> None:
        self._name = name
        self._timeout_s = timeout_s
        self._startup_timeout_s = timeout_s if startup_timeout_s is None else startup_timeout_s
        self._on_stall = on_stall
        self._probe = probe
        self._poll_s = poll_s
        self._last = time.monotonic()
        self._moved = False
        self._task: asyncio.Task[None] | None = None

    def beat(self) -> None:
        """Say the watched thing just moved. Callable from any thread, never waits."""
        self._last = time.monotonic()
        self._moved = True

    def rearm(self) -> None:
        """Start the coming-up budget again from now (trap 13): the first byte counts
        from the tap, not the earlier pipe."""
        self._last = time.monotonic()
        self._moved = False

    def start(self) -> None:
        """Begin watching, from the event loop. The clock starts here."""
        if self._task is not None:
            return
        self._last = time.monotonic()
        self._task = asyncio.get_running_loop().create_task(self._run(), name=f"wd-{self._name}")

    async def aclose(self) -> None:
        """Stop watching. Idempotent, and safe from inside the reaction itself."""
        task, self._task = self._task, None
        if task is None or task.done() or task is asyncio.current_task():
            return  # inside on_stall: cancelling would cancel the running reaction
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._poll_s)
            stall = self._look()
            if stall is None:
                continue
            logger.warning("the %s watchdog fired: %s", self._name, stall.reason)
            try:
                await self._on_stall(stall)
            except Exception:
                logger.exception("the %s watchdog's reaction failed", self._name)
            return

    def _look(self) -> Stall | None:
        silent_for = time.monotonic() - self._last
        reason = self._probe() if self._probe is not None else None
        if reason is not None:
            return Stall(self._name, reason, silent_for)
        if self._moved:
            if silent_for > self._timeout_s:
                return Stall(self._name, f"nothing moved for {silent_for:.1f}s", silent_for)
        elif silent_for > self._startup_timeout_s:
            reason = f"nothing ever arrived, {silent_for:.1f}s after it was armed"
            return Stall(self._name, reason, silent_for)
        return None
