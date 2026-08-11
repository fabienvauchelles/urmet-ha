"""Asking again for a picture the panel has not brought up yet.

The panel brings video up a moment after the call reaches ``streaming``, so a
session opened inside that window finds none and the stack refuses the tap; sampling
once would make whether a visitor is seen a matter of clicking speed, so this asks
again on a cadence. Three answers: the picture arrives; or the dialog carries no
video line at all (``NoVideoOfferedError``, terminal, trap 14); or the owner stops
it. The generation recorded at ``start`` guards trap 15: arming refuses a moved one.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress

from urmet_sdk import CallError, NoVideoOfferedError, VideoFormat

logger = logging.getLogger(__name__)

# Every crossing runs on the single SDK worker thread (with every hangup, mute and
# open), so the cadence is a budget: a second is invisible, a tighter one crowds it.
RETRY_INTERVAL_S = 1.0


class PictureWait:
    """One session's standing question: is there a picture yet. ``first_delay_s``
    holds the first look off, because a recorder armed into the panel's opening size
    change waits nine seconds for the next keyframe (measured)."""

    def __init__(
        self,
        *,
        name: str,
        ask: Callable[[int], Awaitable[VideoFormat]],
        on_arrived: Callable[[VideoFormat], None],
        on_never: Callable[[str], Awaitable[None]],
        first_delay_s: float,
    ) -> None:
        self._name = name
        self._ask = ask
        self._on_arrived = on_arrived
        self._on_never = on_never
        self._first_delay_s = first_delay_s
        self._waiting = False
        self._reason = ""
        self._generation = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def waiting(self) -> bool:
        """Whether a picture is still being asked for."""
        return self._waiting

    @property
    def reason(self) -> str:
        """What the stack last answered, in words a page can show."""
        return self._reason

    @property
    def generation(self) -> int:
        return self._generation

    def start(self, reason: str, generation: int) -> None:
        """Begin asking against ``generation``. ``reason`` is what a page shows."""
        self._waiting = True
        self._reason = reason
        self._generation = generation
        logger.warning("session %s has no picture yet: %s", self._name, reason)
        task = asyncio.get_running_loop().create_task(
            self._keep_asking(), name=f"urmet-video-wait-{self._name}"
        )
        task.add_done_callback(self._finished)
        self._task = task

    async def stop(self) -> None:
        """End the asking. Idempotent; safe from inside the asking itself (it can give
        up on its own, so cancelling from within only drops the reference).
        """
        self._waiting = False
        task, self._task = self._task, None
        if task is None or task is asyncio.current_task():
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _keep_asking(self) -> None:
        """Ask until the picture is given, or until asking cannot help."""
        delay = self._first_delay_s
        while self._waiting:
            await asyncio.sleep(delay)
            delay = RETRY_INTERVAL_S
            if not self._waiting:
                return
            try:
                geometry = await self._ask(self._generation)
            except NoVideoOfferedError as error:
                # No video line at all, which no asking turns into one (trap 14).
                self._waiting = False
                await self._on_never(str(error))
                return
            except CallError as error:
                # Retryable, including a stale arm the generation guard refused; the
                # loop guard ends that once ``stop`` lowers ``waiting`` (trap 15).
                self._reason = str(error)
                logger.debug("session %s still without a picture: %s", self._name, error)
                continue
            self._waiting = False
            self._reason = ""
            self._on_arrived(geometry)
            return

    def _finished(self, task: asyncio.Task[None]) -> None:
        # Whatever the asking raised is written down here, or nowhere at all.
        self._task = None
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("session %s stopped asking for a picture", self._name, exc_info=error)
