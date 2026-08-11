"""Doubles and helpers for the WP4 video-path scenarios.

A tap that records every crossing and never opens a real pipe, and a stand-in for
ffmpeg so no scenario but the Annex B one spawns the encoder. Both keep the video
path exercised end to end (real FIFO, real child, real demux thread) while leaving
the panel and the SDK out of it, exactly as ``tests/isolation`` leaves the network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from urmet_sdk import CallError, NoVideoOfferedError, VideoFormat

from urmet_gateway.media import encoder

# A child that stays up and silent (a pipeline waiting to be tapped) and one that
# is already gone (the encoder the watchdog is there to notice). coreutils, so this
# file starts no interpreter and carries no second copy of anything.
HOLD_S = 3600
LIVE = ("sleep", str(HOLD_S))
DEAD = ("false",)
DEAD_EXIT_CODE = 1

DEFAULT_FORMAT = VideoFormat(width=320, height=240)


def _stand_in(program: tuple[str, ...]) -> Callable[[Path], list[str]]:
    def argv(_pipe: Path) -> list[str]:
        # The pipe is ignored: the stand-in never reads it, so it does not block on
        # a FIFO the fake tap never writes to.
        return list(program)

    return argv


@contextmanager
def stand_in_encoder(*, alive: bool = True) -> Iterator[None]:
    """Run a coreutils child instead of ffmpeg for the duration of the block."""
    original = encoder.encoder_argv
    encoder.encoder_argv = _stand_in(LIVE if alive else DEAD)
    try:
        yield
    finally:
        encoder.encoder_argv = original


class FakeVideoTap:
    """A ``VideoTap`` that records every crossing and never opens a real pipe.

    ``open_video`` can be told to refuse (a plain ``CallError``) until a stream is
    up, to carry no video line at all (``NoVideoOfferedError``), or to run a hook in
    the middle of the crossing, which is how the generation race is provoked.
    """

    def __init__(self, *, video_format: VideoFormat = DEFAULT_FORMAT) -> None:
        self.video_format = video_format
        self.opens: list[tuple[Path, int]] = []
        self.closes = 0
        self.available = True
        self.offered = True
        self.during_open: Callable[[], Awaitable[None]] | None = None

    async def open_video(self, sink_path: Path, generation: int) -> VideoFormat:
        if self.during_open is not None:
            hook, self.during_open = self.during_open, None
            await hook()
        if not self.offered:
            raise NoVideoOfferedError("call 1 was placed without video, so there is none to tap")
        if not self.available:
            raise CallError("call 1 carries no video stream to tap")
        self.opens.append((sink_path, generation))
        return self.video_format

    async def close_video(self) -> None:
        self.closes += 1


async def eventually(
    predicate: Callable[[], object], *, timeout: float = 3.0, tick: float = 0.01
) -> None:
    """Wait until ``predicate`` is truthy, or fail saying it never was."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        assert loop.time() < deadline, "the condition was not met inside the deadline"
        await asyncio.sleep(tick)
