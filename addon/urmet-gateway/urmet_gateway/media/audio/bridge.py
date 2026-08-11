"""Where pjmedia's clock thread and the event loop meet, and what it costs.

``AudioBridge`` is the SDK's ``AudioSink``: ``on_frame`` and ``next_frame`` are
entered from pjmedia's clock thread while it holds the conference bridge's lock,
fifty times a second each way. They copy one frame into or out of a bounded
deque, count it, and return. No lock the event loop can hold, nothing unbounded,
never a wait: waiting stalls the clock for every other port on the bridge. When
the browser supplied nothing ``next_frame`` answers None and the stack sends
silence, a late frame being worse than a silent one. The only asyncio crossing
is ``call_soon_threadsafe``, made only when a reader waits (see ``_wake``); the
counters are doubled so a stopped sender shows as the first climbing, second still.
"""

import asyncio
import time
from collections import deque
from contextlib import suppress

from urmet_sdk import AudioFormat

# How much audio either direction may hold before the oldest frame is dropped.
# Twenty frames is 400 ms, past which a voice path is no longer a voice path, so
# a consumer that fell behind loses the backlog rather than replaying it late.
BACKLOG_FRAMES = 20

# How many callback timings are kept for the percentile. At fifty a second in
# each direction this is a rolling twenty seconds, held in a list whose length
# never changes, so the clock thread writes it while the caller reads it.
TIMING_WINDOW = 2000

_P99 = 0.99


class Timings:
    """What the callbacks cost, written by one thread and read by another.

    A fixed list and a moving index, not a growing buffer, because the reader
    copies the window while the clock thread writes it.
    """

    def __init__(self, window: int = TIMING_WINDOW) -> None:
        self._window = window
        self._samples = [0.0] * window
        self._at = 0
        self._filled = 0
        self.max_s = 0.0

    def record(self, seconds: float) -> None:
        """Keep one callback's duration. Media clock thread, so no allocation."""
        self._samples[self._at] = seconds
        self._at = (self._at + 1) % self._window
        if self._filled < self._window:
            self._filled += 1
        if seconds > self.max_s:
            self.max_s = seconds

    def p99_s(self) -> float:
        """The 99th percentile of the window, or 0.0 while nothing was timed."""
        filled = self._filled
        if not filled:
            return 0.0
        ordered = sorted(self._samples[:filled])
        return ordered[min(filled - 1, int(filled * _P99))]


class AudioBridge:
    """One call's audio in both directions, across the clock thread boundary.

    Built on the event loop, because it captures the loop it wakes. Handed to
    ``MediaTap.attach_audio_tap`` as the ``AudioSink``.
    """

    def __init__(self, audio_format: AudioFormat, *, backlog: int = BACKLOG_FRAMES) -> None:
        self._loop = asyncio.get_running_loop()
        self._format = audio_format
        self._backlog = backlog
        self._downlink: deque[bytes] = deque(maxlen=backlog)
        self._uplink: deque[bytes] = deque(maxlen=backlog)
        self._arrival = asyncio.Event()
        self._waiting = False
        self._closed = False
        self.timings = Timings()
        self.received = 0
        self.supplied = 0
        self.underruns = 0
        self.dropped_downlink = 0
        self.dropped_uplink = 0
        self.unreachable_loop = 0
        self.packets_delivered = 0
        self.partial_frames = 0
        self.stop_reason = ""

    @property
    def audio_format(self) -> AudioFormat:
        """The PCM the tap said it exchanges, and the size of one frame."""
        return self._format

    # -- the media clock thread: copy and return, never wait ---------------

    def on_frame(self, pcm: bytes) -> None:
        """Take one frame from the doorphone. Media clock thread, never raises."""
        started = time.perf_counter()
        if len(self._downlink) == self._backlog:
            self.dropped_downlink += 1
        self._downlink.append(pcm)
        self.received += 1
        if self._waiting:
            self._wake()
        self.timings.record(time.perf_counter() - started)

    def _wake(self) -> None:
        """Schedule the wake-up a waiting reader is owed. Media clock thread.

        The flag is lowered here rather than by the reader, so a loop that is not
        turning collects one handle for the whole stall. No frame is lost behind
        it: the reader clears the event, raises the flag, and looks once more
        before it sleeps, so a frame appended before that look is seen, one
        appended after finds the flag raised and is signalled, and a signal made
        between the clear and the sleep leaves the event set.
        """
        self._waiting = False
        try:
            self._loop.call_soon_threadsafe(self._arrival.set)
        except RuntimeError:
            # The loop closed under a call that is still streaming. Counted and
            # reported, never raised: an exception here unwinds into C++.
            self.unreachable_loop += 1

    def next_frame(self) -> bytes | None:
        """Supply one frame for the doorphone. Media clock thread, never raises.

        None whenever the browser supplied nothing: the stack reads that as
        silence, the normal state of a muted page, and it is answered at once.
        """
        started = time.perf_counter()
        try:
            pcm: bytes | None = self._uplink.popleft()
            self.supplied += 1
        except IndexError:
            pcm = None
            self.underruns += 1
        self.timings.record(time.perf_counter() - started)
        return pcm

    # -- the event loop ----------------------------------------------------

    async def next_downlink(self) -> bytes | None:
        """One frame from the doorphone, or None once the bridge is closed."""
        while True:
            with suppress(IndexError):
                return self._downlink.popleft()
            if self._closed:
                return None
            # This order is the contract ``_wake`` reads: clear the event, ask
            # to be woken, look at the deque once more, and only then sleep.
            self._arrival.clear()
            self._waiting = True
            if not self._downlink and not self._closed:
                await self._arrival.wait()
            self._waiting = False

    def push_uplink(self, pcm: bytes) -> None:
        """Queue one frame for the doorphone, dropping the oldest when full.

        Full is the ordinary state of a muted call: the port is off the bridge,
        so this holds the last 400 ms and unmuting sends what was just said.
        """
        if len(self._uplink) == self._backlog:
            self.dropped_uplink += 1
        self._uplink.append(pcm)

    def close(self) -> None:
        """End the downlink so a track waiting on it wakes. Event loop thread."""
        self._closed = True
        self._arrival.set()

    # -- what the downlink track reports back ------------------------------

    def delivered(self) -> None:
        """One packet reached aiortc. Event loop thread, from the track."""
        self.packets_delivered += 1

    def partial_frame(self) -> None:
        """The panel sent a frame that was not whole samples. Event loop thread."""
        self.partial_frames += 1

    def stopped(self, reason: str) -> None:
        """The downlink track ended, and why. The first reason is the one kept."""
        if not self.stop_reason:
            self.stop_reason = reason
