"""The video downlink: the panel's picture, encoded once, on its way to a browser.

``start`` makes the pipe and encoder and creates the track; ``arm`` is then the one
and only way the video tap is opened onto that pipe (trap 2), because the generation
counter (trap 15) checks arming against rebuilding: ``arm`` refuses a generation the
pipeline moved past, so a retry in flight cannot open a recorder onto a pipe a rebuild
or stall just killed. ``encoder`` is replaced whole on a rebuild; ``track`` is not (it
carries the timeline); ``watchdog`` reacts here.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from av.packet import Packet
from av.video.stream import VideoStream
from urmet_sdk import VideoFormat

from urmet_gateway.domain.errors import (
    CallError,
    DownlinkNotDrainingError,
    DownlinkNotStartedError,
    StaleArmError,
)
from urmet_gateway.media.encoder import EncoderRun
from urmet_gateway.media.track import VideoPacketTrack
from urmet_gateway.media.watchdog import Stall, Watchdog

logger = logging.getLogger(__name__)

# How long a running stream may go quiet before the plug is pulled. Short because
# a pipe nobody drains blocks pjmedia's clock thread, and the conversation with it.
SILENCE_TIMEOUT_S = 8.0

# How long a pipeline that never delivered anything is given to come up. Measured:
# the recorder writes nothing for ~4 s after the tap and the first byte lands ~10 s,
# so it needs a budget of its own (sharing the silence one killed pipelines early).
STARTUP_TIMEOUT_S = 25.0


class VideoTap(Protocol):
    """The two video crossings the downlink needs, thread hop made and call handle
    bound by the sip layer's ``WorkerTap``. ``open_video`` takes no size argument
    (WorkerTap owns ``MAX_TAP_BYTES``, trap 1) and carries the generation.
    """

    async def open_video(self, sink_path: Path, generation: int) -> VideoFormat: ...

    async def close_video(self) -> None: ...


class VideoDownlink:
    """One call's picture: a pipe to be tapped, a track to be sent, and the watchdog
    and generation counter that keep the two honest."""

    def __init__(
        self,
        tap: VideoTap,
        *,
        on_stall: Callable[[Stall], Awaitable[None]] | None = None,
        silence_timeout_s: float = SILENCE_TIMEOUT_S,
        startup_timeout_s: float = STARTUP_TIMEOUT_S,
    ) -> None:
        self._tap = tap
        self._on_stall = on_stall
        self._silence_timeout_s = silence_timeout_s
        self._startup_timeout_s = startup_timeout_s
        self._track: VideoPacketTrack | None = None
        self._run: EncoderRun | None = None
        self._watchdog: Watchdog | None = None
        self._generation = 0

    @property
    def track(self) -> VideoPacketTrack:
        """The track to add to the peer connection. It outlives every rebuild."""
        return self._require_track()

    @property
    def pipe_path(self) -> Path:
        if self._run is None:
            raise DownlinkNotStartedError("the video downlink has no pipe open")
        return self._run.pipe_path

    @property
    def generation(self) -> int:
        """Monotonic token; moves on every (re)build and every stop (trap 15)."""
        return self._generation

    @property
    def sent(self) -> int:
        return 0 if self._track is None else self._track.sent

    @property
    def dropped(self) -> int:
        return 0 if self._track is None else self._track.dropped

    async def start(self) -> VideoPacketTrack:
        """Make the pipe and encoder, create the track, start watching. The track is
        created once (it outlives every rebuild); nothing flows until ``arm`` takes."""
        if self._track is None:
            self._track = VideoPacketTrack(asyncio.get_running_loop())
        await self._start_run()
        return self._track

    async def arm(self, generation: int) -> VideoFormat:
        """The one way a tap is ever opened (trap 2). Refuses unless the encoder is
        draining and refuses a stale generation (trap 15) before and after the crossing,
        closing anything a race left armed on a dead pipe; then rearms the watchdog."""
        if generation != self._generation:
            raise StaleArmError(f"arm for generation {generation} is stale ({self._generation})")
        run = self._run
        if run is None or not run.draining:
            raise DownlinkNotDrainingError("no encoder is draining the pipe to arm the tap on")
        fmt = await self._tap.open_video(run.pipe_path, generation)
        if generation != self._generation:
            # A rebuild or a stall moved the pipeline out from under this arm while
            # it crossed; what we just opened is on a pipe now dead, so close it.
            with suppress(CallError, OSError):
                await self._tap.close_video()
            raise StaleArmError(f"arm for generation {generation} raced a rebuild")
        if self._watchdog is not None:
            self._watchdog.rearm()
        return fmt

    async def restart(self) -> None:
        """Rebuild the pipe and encoder for a size change, on a new pipe (the recorder
        fixes geometry in the header). The track and its timeline are untouched, so the
        browser sees one stream; the generation moves, so any arm on the old pipe fails.
        """
        self._require_track()
        await self._stop_run()
        await self._start_run()

    async def aclose(self) -> None:
        """Tear the pipeline down and end the track. Idempotent."""
        await self._stop_run()
        if self._track is not None:
            self._track.stop()

    def _require_track(self) -> VideoPacketTrack:
        if self._track is None:
            raise DownlinkNotStartedError("the video downlink has not been started")
        return self._track

    async def _start_run(self) -> None:
        self._generation += 1
        run = EncoderRun(self._receive)
        try:
            run.start()
        except OSError:
            # No ffmpeg, or a pipe that could not be made: leave nothing behind.
            await run.stop()
            raise
        self._run = run
        watchdog = Watchdog(
            name="video",
            timeout_s=self._silence_timeout_s,
            startup_timeout_s=self._startup_timeout_s,
            on_stall=self._pull_the_plug,
            probe=self._encoder_gone,
        )
        watchdog.start()
        self._watchdog = watchdog

    def _receive(self, packet: Packet[VideoStream]) -> None:
        """One packet off the demux thread: feed the watchdog, stamp the track."""
        watchdog = self._watchdog
        if watchdog is not None:
            watchdog.beat()
        track = self._track
        if track is not None:
            track.submit(packet)

    def _encoder_gone(self) -> str | None:
        run = self._run
        if run is None:
            return None
        code = run.exit_code()
        return None if code is None else f"the encoder exited with {code}"

    async def _pull_the_plug(self, stall: Stall) -> None:
        """The watchdog fired: kill ffmpeg first (EPIPE for the recorder, not a blocked
        clock thread), then tell the owner so it can stop asking and close the tap,
        then tear the pipeline down."""
        logger.error("the video downlink stalled: %s", stall.reason)
        if self._run is not None:
            self._run.kill()
        if self._on_stall is not None:
            await self._on_stall(stall)
        await self._stop_run()

    async def _stop_run(self) -> None:
        watchdog, self._watchdog = self._watchdog, None
        if watchdog is not None:
            await watchdog.aclose()
        run, self._run = self._run, None
        if run is not None:
            self._generation += 1
            await run.stop()
