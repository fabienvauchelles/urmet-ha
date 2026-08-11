"""The one thread every SDK call crosses.

The SDK is threaded and blocking: a REGISTER waits for the registrar, a view
waits for the media, an open waits for the 200 OK. This gateway is asyncio, so
every one of those calls is submitted to a single dedicated thread and awaited.

One thread and not a pool, for two reasons. Calls serialise, so the native
transport is announced to exactly one foreign thread and two REGISTERs can never
overlap. And the event loop never blocks, which is what lets a doorbell reach a
browser while a call is being placed.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class WorkerStoppedError(RuntimeError):
    """An SDK call was submitted after the worker had been shut down."""


class SdkWorker:
    """Runs blocking SDK calls on a single thread and hands the result back."""

    def __init__(self, *, thread_name: str = "urmet-sdk") -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=thread_name)
        self._active = 0
        self._stopped = False

    @property
    def busy(self) -> bool:
        """True while a call is queued on or running through the one thread.

        The registration supervisor reads this before a reconnect attempt: a
        retry that would only queue behind a user command is deferred instead,
        so the backoff never advances for an attempt that was never made.
        """
        return self._active > 0

    async def run(self, call: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Run ``call`` on the worker thread and return what it returned.

        Whatever the SDK raises is re-raised here unchanged, traceback included,
        so a caller matches ``NotRegisteredError`` or ``OpenNotAcknowledgedError``
        without unwrapping anything.

        Cancelling the await stops the waiting, not the call: a native request
        already on the wire runs to its end on the worker thread, because there
        is no way to interrupt it that leaves the stack usable afterwards.
        """
        if self._stopped:
            name = getattr(call, "__qualname__", repr(call))
            raise WorkerStoppedError(f"the SDK worker is stopped; {name} was not run")
        loop = asyncio.get_running_loop()
        self._active += 1
        try:
            return await loop.run_in_executor(
                self._executor, functools.partial(call, *args, **kwargs)
            )
        finally:
            self._active -= 1

    async def aclose(self) -> None:
        """Drop what is queued, wait for what is running, and join the thread.

        Idempotent. The join happens on another thread so the event loop keeps
        turning while the last SDK call finishes, and the process is left with no
        thread of ours alive.
        """
        if self._stopped:
            return
        self._stopped = True
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)
        logger.debug("SDK worker thread joined")
