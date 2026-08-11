"""The two ends aiortc drives, and everything they write down on the bridge.

Neither direction converts a sample. The downlink hands aiortc packets, exactly
as the video track hands it H.264 packets, and the uplink takes aiortc's decoded
PCMA, already the s16 mono 8 kHz the tap asks for, and re-cuts it into frames of
the size the stack wants. ``g711`` says what the one companding table is for.

The downlink timeline is a sample counter that only moves forward, so a restart
cannot put a packet in the past and starve the loop with no error and no output.

Every way ``recv`` can end is reported to the bridge, and that is not tidiness.
aiortc's sender catches everything a track raises that is not a
``MediaStreamError``, writes one warning to a logger of its own, and never calls
that track again. The panel's frames go on crossing the clock thread and being
counted the whole time, so from outside a sender it stopped and a sender that is
working read exactly the same: media negotiated, bytes moving, nothing arriving,
nobody told. So the hand-over is counted where the video track counts its own,
and a track that stopped says so instead of leaving it to be inferred.
"""

from __future__ import annotations

import logging
from contextlib import suppress

import av
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
from av.frame import Frame
from av.packet import Packet
from av.stream import Stream

from urmet_gateway.media.audio.bridge import AudioBridge
from urmet_gateway.media.audio.g711 import PCMA_TIME_BASE, to_alaw

logger = logging.getLogger(__name__)

_BYTES_PER_SAMPLE = 2


class UplinkFormatError(ValueError):
    """The browser's track decoded to PCM the doorphone's tap cannot take."""


class DoorphoneAudioTrack(MediaStreamTrack):
    """The panel's voice as PCMA packets, which aiortc sends without encoding."""

    kind = "audio"

    def __init__(self, bridge: AudioBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._timestamp = 0

    async def recv(self) -> Packet[Stream]:
        """One packet for aiortc, and one line on the bridge for every ending."""
        try:
            packet = await self._next_packet()
        except MediaStreamError as ended:
            self._bridge.stopped(str(ended) or "the doorphone audio track ended")
            raise
        except Exception as failure:
            # aiortc keeps this to its own logger and stops the track for good,
            # so the session either learns it here or never learns it at all.
            logger.exception("the doorphone audio track failed")
            self._bridge.stopped(f"the doorphone audio track failed: {failure}")
            raise
        self._bridge.delivered()
        return packet

    async def _next_packet(self) -> Packet[Stream]:
        """The next frame carrying a whole sample, as an A-law packet."""
        if self.readyState != "live":
            raise MediaStreamError("the doorphone audio track has ended")
        payload = b""
        while not payload:
            pcm = await self._bridge.next_downlink()
            if pcm is None:
                raise MediaStreamError("the doorphone audio bridge was closed")
            payload = to_alaw(pcm)
            if len(payload) * _BYTES_PER_SAMPLE != len(pcm):
                self._bridge.partial_frame()
        packet: Packet[Stream] = Packet(payload)
        packet.pts = self._timestamp
        packet.time_base = PCMA_TIME_BASE
        # One A-law byte is one sample, so the payload's length is what the RTP
        # clock advances by. A counter cannot go backwards across a restart.
        self._timestamp += len(payload)
        return packet


class BrowserAudioPump:
    """The browser's voice, from aiortc's decoded PCMA into the tap's frames.

    aiortc decodes a received track before the caller sees it, so this end takes
    frames rather than packets. It is a passthrough all the same: PCMA decodes to
    the s16 mono 8 kHz the tap wants, so the only work is re-cutting the bytes.
    """

    def __init__(self, bridge: AudioBridge, track: MediaStreamTrack) -> None:
        self._bridge = bridge
        self._track = track
        self._pending = bytearray()
        self._frame_bytes = bridge.audio_format.frame_bytes
        self.frames = 0

    async def run(self) -> None:
        """Drain the browser's track until it ends. Raises on unexpected PCM."""
        with suppress(MediaStreamError):
            while True:
                self._take(await self._track.recv())

    def _take(self, frame: Frame | Packet[Stream]) -> None:
        """Cut one decoded frame into whole tap frames, converting nothing."""
        wanted = self._bridge.audio_format
        if not isinstance(frame, av.AudioFrame):
            raise UplinkFormatError(f"the browser's audio track yielded {type(frame).__name__}")
        if (
            frame.format.name != "s16"
            or frame.layout.name != "mono"
            or frame.sample_rate != wanted.clock_rate
        ):
            raise UplinkFormatError(
                f"the browser's audio decoded to {frame.format.name} {frame.layout.name} at "
                f"{frame.sample_rate} Hz, and this bridge carries s16 mono at "
                f"{wanted.clock_rate} Hz without converting a sample"
            )
        self._pending += bytes(frame.planes[0])[: frame.samples * _BYTES_PER_SAMPLE]
        while len(self._pending) >= self._frame_bytes:
            self._bridge.push_uplink(bytes(self._pending[: self._frame_bytes]))
            del self._pending[: self._frame_bytes]
            self.frames += 1
