"""The track aiortc pulls from, and the clock it is timed on.

Packets, not frames. The picture arrives already encoded and aiortc packs what
it is given rather than encoding it again, which is what keeps one re-encode in
the whole path.

The timeline is the part that has to be right. A packet's presentation time is
when it came out of the demuxer, on the process clock, taken once when the track
is built and never reset. That makes the track outlive every rebuild of the pipe
and the encoder underneath it, and it makes going backwards impossible rather
than unlikely: timestamps that move back leave every packet late, ``recv`` stops
awaiting, and the loop starves with no error and no output at all (trap 8).

Arrival is also the only honest clock. The pj recorder writes an AVI header
claiming fifteen frames a second whatever the panel really sends (about seven),
so a timeline read out of that file would run at the wrong rate and the browser's
playout would drift steadily away from the conversation.
"""

from __future__ import annotations

import asyncio
import fractions
import logging
import time
from contextlib import suppress

from aiortc import RTCPeerConnection, RTCRtpSender
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
from aiortc.rtcrtpparameters import RTCRtpCodecCapability
from av.packet import Packet
from av.video.stream import VideoStream

from urmet_gateway.domain.errors import H264UnavailableError

logger = logging.getLogger(__name__)

# The RTP clock every H.264 payload is timed on.
VIDEO_CLOCK_RATE = 90000
RTP_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)

# Deep enough to ride out a busy loop, shallow enough that what it holds is still
# worth sending by the time the loop comes back. Full queue drops the oldest.
QUEUE_DEPTH = 60

# What may stay on the video line: the codec the panel already speaks, and the
# retransmission stream that repairs it.
H264_MIME = "video/H264"
RTX_MIME = "video/rtx"


class VideoPacketTrack(MediaStreamTrack):
    """Hands aiortc packets that are already encoded, on a forward-only clock.

    Built once and kept for the life of the call, because it is what carries the
    timeline across a rebuild.
    """

    kind = "video"

    def __init__(self, loop: asyncio.AbstractEventLoop, *, depth: int = QUEUE_DEPTH) -> None:
        super().__init__()
        self._owner_loop = loop
        self._queue: asyncio.Queue[Packet[VideoStream] | None] = asyncio.Queue(maxsize=depth)
        self._origin = time.monotonic()
        self._last_ticks = -1
        self._sent = 0
        self._dropped = 0

    @property
    def sent(self) -> int:
        """How many packets have been handed to aiortc."""
        return self._sent

    @property
    def dropped(self) -> int:
        """How many packets were dropped because the loop fell behind."""
        return self._dropped

    def submit(self, packet: Packet[VideoStream]) -> None:
        """Stamp one packet and hand it to the loop. Called from the demux thread.

        The stamp is taken here rather than on the loop, so a busy loop shows up
        as jitter in delivery and never as jitter in the timeline. It is forced
        strictly upwards: two packets read in the same instant come out one tick
        apart, and no arithmetic here can produce a value below the one before it.
        """
        if self.readyState != "live":
            return
        ticks = max(self._last_ticks + 1, int((time.monotonic() - self._origin) * VIDEO_CLOCK_RATE))
        self._last_ticks = ticks
        packet.pts = ticks
        packet.time_base = RTP_TIME_BASE
        try:
            self._owner_loop.call_soon_threadsafe(self._enqueue, packet)
        except RuntimeError:
            # The loop was closed under us during teardown. There is nothing
            # downstream left to hand a packet to, and that is not a failure.
            return

    def _enqueue(self, packet: Packet[VideoStream]) -> None:
        """Put one packet in front of aiortc, dropping the oldest when full."""
        if self._queue.full():
            self._queue.get_nowait()
            self._dropped += 1
            if self._dropped == 1:
                logger.warning("the video queue is full; the oldest packets are being dropped")
        self._queue.put_nowait(packet)

    async def recv(self) -> Packet[VideoStream]:
        """One packet for aiortc, waiting for the next one when there is none."""
        packet = await self._queue.get()
        if packet is None or self.readyState != "live":
            raise MediaStreamError
        # The source is live, so a packet is due the moment it exists and pacing
        # it further would only add latency. The yield is the part that matters:
        # a burst must not be handed over without the loop turning in between,
        # which is how a sender starves everything sharing its loop.
        await asyncio.sleep(0)
        self._sent += 1
        return packet

    def stop(self) -> None:
        """End the track, waking whatever was waiting on the next packet."""
        super().stop()
        with suppress(RuntimeError):
            self._owner_loop.call_soon_threadsafe(self._queue.put_nowait, None)


def pin_h264(pc: RTCPeerConnection) -> list[RTCRtpCodecCapability]:
    """Make H.264 the only video codec offered, and say which ones those are.

    aiortc publishes VP8 first and H.264 third, and negotiation takes the first
    codec both ends know, so a track handing over H.264 packets on a VP8 line
    sends steadily and delivers nothing.

    When, and it is not a detail: the transceivers have to exist, so this comes
    after ``addTrack``, and the preference has to be in place before
    ``setRemoteDescription``, because that is where aiortc settles the common
    codec list and it never revisits it. Pinned afterwards, nothing raises and
    the browser decodes not one frame.
    """
    codecs = [
        codec
        for codec in RTCRtpSender.getCapabilities("video").codecs
        if codec.mimeType in (H264_MIME, RTX_MIME)
    ]
    if not any(codec.mimeType == H264_MIME for codec in codecs):
        raise H264UnavailableError(f"this aiortc build publishes no {H264_MIME} to pin")
    for transceiver in pc.getTransceivers():
        if transceiver.kind == "video":
            transceiver.setCodecPreferences(codecs)
    return codecs
