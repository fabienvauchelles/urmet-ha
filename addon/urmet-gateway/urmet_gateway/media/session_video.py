"""One session's picture: the pipeline, the tap on it, waiting, and losing it.

The order in ``arm`` is not a convention. The pipeline (its FIFO, encoder and demux
thread) is started first and the tap is armed on it only afterwards, because opening
a named pipe for writing blocks until a reader appears, and the reader is that encoder.

Arming is not a sample taken inside ``arm`` either. The panel brings its video up a
moment after the call reaches ``streaming`` and settles on a picture size while doing
it, and the SDK's ``open_video_tap`` refuses to arm until that size has settled. So
``arm`` builds the pipeline, hands the track back, and lets ``PictureWait`` ask again
on a cadence until the stack answers a geometry, which is how a stream the panel brings
up after the answer is still picked up.

Waiting is not degraded. A session that never had a picture and one that had a picture
and lost it are two different things to whoever is looking, so they are two different
states and the layer above reads them apart. The track is the part that does not go
missing: it is created once, handed to the peer connection whether or not the tap
armed, and carries the timeline across every rebuild, because a timeline that moves
backwards leaves every packet late and starves the loop with no error and no output.

The generation counter (trap 15) is the pipeline's own guard: ``arm`` refuses a
generation a rebuild or a stall moved past. The tap the sip layer hands over owns
``MAX_TAP_BYTES`` and needs no generation, so ``_VideoTapAdapter`` drops it on the way
through; the guard stays where the counter lives, in the pipeline.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from urmet_sdk import VideoFormat

from urmet_gateway.domain.ports import TapPort
from urmet_gateway.media.picture_wait import PictureWait
from urmet_gateway.media.pipeline import VideoDownlink
from urmet_gateway.media.track import VideoPacketTrack
from urmet_gateway.media.watchdog import Stall

logger = logging.getLogger(__name__)

FIRST_LOOK = "the panel has not settled on a picture size yet"


class _VideoTapAdapter:
    """Adapts the domain ``TapPort`` to the pipeline's ``VideoTap``.

    The pipeline carries a generation across the crossing for its trap-15 guard;
    the ``TapPort`` the sip layer implements owns ``MAX_TAP_BYTES`` and needs no
    generation, so it is dropped here. The check is the pipeline's, not the tap's.
    """

    def __init__(self, tap: TapPort) -> None:
        self._tap = tap

    async def open_video(self, sink_path: Path, generation: int) -> VideoFormat:
        return await self._tap.open_video(sink_path)

    async def close_video(self) -> None:
        await self._tap.close_video()


class SessionVideo:
    """One session's downlink: armed, waited for, and given up on a stall."""

    def __init__(
        self,
        *,
        name: str,
        tap: TapPort,
        settle_s: float,
        on_lost: Callable[[str], None],
        on_ready: Callable[[], None],
    ) -> None:
        self._name = name
        self._tap = tap
        self._on_lost = on_lost
        self._on_ready = on_ready
        self._downlink = VideoDownlink(_VideoTapAdapter(tap), on_stall=self._stalled)
        self._track: VideoPacketTrack | None = None
        self._geometry: VideoFormat | None = None
        self._reason = ""
        self._wait = PictureWait(
            name=name,
            ask=self._ask,
            on_arrived=self._arrived,
            on_never=self._lose,
            first_delay_s=settle_s,
        )

    @property
    def geometry(self) -> VideoFormat | None:
        """The size being encoded, or None while there is no picture."""
        return self._geometry

    @property
    def waiting(self) -> bool:
        """Whether a first picture has not arrived yet and is still asked for.

        False both before there is anything to wait for and once the picture has
        been given up, so it separates a session still coming up from one that
        lost what it had.
        """
        return self._wait.waiting

    @property
    def sent(self) -> int:
        """Packets handed to aiortc since this session opened."""
        return 0 if self._track is None else self._track.sent

    @property
    def dropped(self) -> int:
        """Packets dropped because the loop fell behind the encoder."""
        return 0 if self._track is None else self._track.dropped

    @property
    def reason(self) -> str:
        """Why there is no picture, whether it is still coming or gone for good."""
        return self._reason or self._wait.reason

    async def arm(self) -> VideoPacketTrack:
        """Start the pipeline, begin waiting for a picture, and hand back the track.

        The tap is not opened here: the first look is a settle later, and the SDK
        refuses a tap until the panel's decoded size stops moving, so the wait's
        own cadence is what arms it once the stream is up. The track is returned
        before there is anything behind it, and the caller adds it to the peer
        connection either way, because aiortc settles the media lines inside
        ``setRemoteDescription`` and never revisits them.
        """
        track = await self._downlink.start()
        self._track = track
        self._wait.start(FIRST_LOOK, self._downlink.generation)
        return track

    async def aclose(self) -> None:
        """Stop asking, close the tap, then the pipeline. Idempotent, safe once gone.

        Every end of a call runs through here, so this is also what stops a
        session asking the stack about a dialog that is already over.
        """
        await self._wait.stop()
        await self._tap.close_video()
        await self._downlink.aclose()

    # -- waiting for a stream that has not come up yet ---------------------

    async def _ask(self, generation: int) -> VideoFormat:
        """One more attempt to arm the tap, for the wait to make on its own.

        The pipeline is still running underneath, so a tap can be armed against a
        pipe that already has a reader. The generation guards trap 15: the wait
        carries the one it started with, and a rebuild that moved it is refused.
        """
        return await self._downlink.arm(generation)

    def _arrived(self, fmt: VideoFormat) -> None:
        """The stream came up and the tap took. Tell the layer above at once."""
        self._geometry = fmt
        self._reason = ""
        logger.info("session %s picked up its picture at %dx%d", self._name, fmt.width, fmt.height)
        self._on_ready()

    # -- losing what was flowing ------------------------------------------

    async def _stalled(self, stall: Stall) -> None:
        """Nothing moved for too long, or the encoder died under us.

        The downlink has already killed ffmpeg, which closes the read end of the
        pipe so the recorder's next write fails rather than blocking the clock
        thread. What is left is to stop asking, close the tap so the panel stops
        writing into a pipe nobody drains, and tell the session it is voice-only.
        The asking stops before the tap is closed so a retry in flight cannot arm
        a recorder onto a pipe this reaction just killed.
        """
        await self._wait.stop()
        await self._tap.close_video()
        await self._lose(stall.reason)

    async def _lose(self, reason: str) -> None:
        """Give up the picture of a session whose voice is still worth having."""
        await self._wait.stop()
        self._geometry = None
        self._reason = reason
        await self._downlink.aclose()
        self._on_lost(reason)
