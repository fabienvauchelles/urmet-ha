"""One WebRTC peer connection, built with a call and torn down with it.

This is where the two legs meet. The panel's picture and voice arrive through the
SDK's media tap, encoded once and never again, and aiortc carries them to a browser
that could never have spoken to the panel itself. Nothing here converts a sample.

The order inside ``answer`` is the whole of this module and none of it is taste. Both
codecs are pinned between ``addTrack`` and ``setRemoteDescription``: a transceiver has
to exist before a preference can be set on it, and aiortc settles the common codec list
inside ``setRemoteDescription`` and never revisits it. Pinned too late, negotiation
takes VP8 and Opus, the tracks hand over H.264 and A-law steadily, nothing raises, and
the far end decodes not one frame. That failure is silent at both ends.

The audio is armed before the answer is built, so an offer that could not open its tap
fails the request rather than answering an SDP that carries nothing. The picture is the
one exception: its track is added whether or not the panel had a stream to give,
because a session that answered without a video line could not be given a picture later
without a fresh offer, and a picture that arrives a second or two late is the normal
case (``session_video`` keeps asking for it).

The teardown order is not negotiable (DESIGN 5.5): the uplink stops first so nothing
more is pushed at the bridge, then the video whose encoder holds the read end of the
pipe, then the audio tap (``detach_audio`` returns only once the stack can no longer be
inside a callback, which is what makes the bridge safe to close), then the peer
connection, whose tracks read from both.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack
from urmet_sdk import AudioFormat

from urmet_gateway.domain.errors import AudioFormatMismatchError, UplinkFormatError
from urmet_gateway.domain.models import AudioFlow, SessionState, SessionView, VideoFlow
from urmet_gateway.domain.ports import MediaChanged, SessionClosed, TapPort
from urmet_gateway.media.audio.bridge import AudioBridge
from urmet_gateway.media.audio.g711 import pin_pcma
from urmet_gateway.media.audio.measure import AudioMeasurement, measure_audio_bridge
from urmet_gateway.media.audio.tracks import BrowserAudioPump, DoorphoneAudioTrack
from urmet_gateway.media.session_video import SessionVideo
from urmet_gateway.media.track import pin_h264

logger = logging.getLogger(__name__)

# The PCM this gateway carries, and the only PCM it carries: PCMA is 8 kHz mono, the
# tap deals in linear 16 bit samples, and pjsua2 hands them over 20 ms at a time. It is
# declared rather than read (the bridge must exist before it is attached) and checked
# against what the tap answers rather than assumed, because the alternative is
# resampling a voice path in silence.
BRIDGE_AUDIO_FORMAT = AudioFormat(clock_rate=8000, channels=1, frame_time_ms=20, bits_per_sample=16)

# The peer-connection states that mean this session is over. "disconnected" is not one
# of them: ICE says so over a lost packet or two and takes it back.
DEAD_CONNECTIONS = frozenset({"failed", "closed"})

ENDED = "the session was ended"


class MediaSession:
    """One browser's view of one call: the peer connection and both bridges."""

    def __init__(
        self,
        *,
        session_id: str,
        call_id: str,
        tap: TapPort,
        video_settle_s: float,
        on_closed: SessionClosed,
        on_media_change: MediaChanged,
    ) -> None:
        self._id = session_id
        self._call_id = call_id
        self._tap = tap
        self._on_closed = on_closed
        self._on_media_change = on_media_change
        self._pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self._video = SessionVideo(
            name=session_id,
            tap=tap,
            settle_s=video_settle_s,
            on_lost=self._picture_lost,
            on_ready=self._picture_ready,
        )
        self._bridge: AudioBridge | None = None
        self._uplink: asyncio.Task[None] | None = None
        self._closed = False
        self._reason = ""
        self._pc.add_listener("track", self._browser_track)
        self._pc.add_listener("connectionstatechange", self._connection_changed)

    # -- what the layer above reads ---------------------------------------

    @property
    def id(self) -> str:
        """The identifier a DELETE names."""
        return self._id

    @property
    def call_id(self) -> str:
        """The dialog this session lives and dies with."""
        return self._call_id

    # -- the one method whose order matters -------------------------------

    async def answer(self, sdp: str) -> str:
        """Arm the media, pin the codecs, and answer the browser's offer.

        Returns the SDP to send back. Raises what the tap raised when the voice
        path could not be armed; the caller closes the session on the way out. A
        picture the panel has not brought up yet is not one of those: the video
        line is negotiated all the same and ``session_video`` keeps asking.
        """
        await self._arm_audio()
        track = await self._video.arm()
        self._pc.addTrack(track)
        self._pc.addTrack(DoorphoneAudioTrack(self._require_bridge()))
        pin_h264(self._pc)
        pin_pcma(self._pc)
        await self._pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        await self._pc.setLocalDescription(await self._pc.createAnswer())
        return str(self._pc.localDescription.sdp)

    async def aclose(self, *, reason: str = ENDED) -> None:
        """Tear the session down, in the order the stack needs. Idempotent."""
        if self._closed:
            return
        self._closed = True
        self._reason = reason
        await self._stop_uplink()
        await self._video.aclose()
        await self._tap.detach_audio()
        if self._bridge is not None:
            self._bridge.close()
        await self._pc.close()
        logger.info("session %s closed: %s", self._id, reason)
        self._on_closed(self, reason)

    def view(self) -> SessionView:
        """One session as the interface and the integration both read it.

        The counters are the honest ones: packets sent is what aiortc was handed,
        frames from the doorphone is what crossed the media clock thread. A voice
        that stopped is said outright, because the browser goes deaf the instant
        aiortc gives up on the downlink track while the bridge keeps counting.
        """
        audio = None if self._bridge is None else measure_audio_bridge(self._bridge)
        return SessionView(
            session_id=self._id,
            call_id=self._call_id,
            state=self._state(audio),
            connection=str(self._pc.connectionState),
            reason=self._reason or self._video.reason or self._voice_lost(audio),
            video=self._video_flow(),
            audio=self._audio_flow(audio),
        )

    # -- arming -----------------------------------------------------------

    async def _arm_audio(self) -> None:
        """Attach the bridge, and refuse PCM this path would have to convert."""
        bridge = AudioBridge(BRIDGE_AUDIO_FORMAT)
        reported = await self._tap.attach_audio(bridge)
        if reported != BRIDGE_AUDIO_FORMAT:
            await self._tap.detach_audio()
            raise AudioFormatMismatchError(
                f"the tap exchanges {reported.clock_rate} Hz PCM in {reported.channels} channels "
                f"of {reported.bits_per_sample} bits every {reported.frame_time_ms} ms, and this "
                "bridge carries A-law without converting a sample"
            )
        self._bridge = bridge

    # -- what the browser and the pipeline report back --------------------

    def _browser_track(self, track: MediaStreamTrack) -> None:
        """The browser's own track arrived, during ``setRemoteDescription``."""
        if track.kind != "audio" or self._bridge is None:
            return
        self._uplink = asyncio.create_task(
            self._drain(BrowserAudioPump(self._bridge, track)),
            name=f"urmet-uplink-{self._id}",
        )

    async def _drain(self, pump: BrowserAudioPump) -> None:
        """Carry the browser's voice to the panel until its track ends.

        A background task has no caller to raise into, so PCM this bridge cannot
        take is written down here rather than surfacing at some later collection.
        The rest of the session carries on: the visitor is still seen and heard.
        """
        try:
            await pump.run()
        except UplinkFormatError:
            logger.exception("session %s refused the browser's uplink", self._id)

    async def _connection_changed(self) -> None:
        """ICE and DTLS moved. A leg that failed takes the session with it."""
        state = self._pc.connectionState
        logger.debug("session %s connection is %s", self._id, state)
        if state in DEAD_CONNECTIONS:
            await self.aclose(reason=f"the browser connection is {state}")

    def _picture_lost(self, reason: str) -> None:
        """The video half gave up. The conversation is not over, so say so."""
        if self._closed:
            return
        logger.warning("session %s lost its picture: %s", self._id, reason)
        self._on_media_change(self, reason)

    def _picture_ready(self) -> None:
        """The picture this session was waiting for arrived. Same notice, no reason."""
        if self._closed:
            return
        self._on_media_change(self, "")

    # -- how a running session reads on the wire --------------------------

    def _state(self, audio: AudioMeasurement | None) -> SessionState:
        """Closed, voice only (degraded), still coming (waiting), or open.

        A voice that stopped outranks any picture: a session that cannot be heard
        is degraded whatever its picture is doing. The two ways to have no picture
        are told apart, because they are not the same to look at: one is still
        coming (waiting), the other is gone (degraded).
        """
        if self._closed:
            return SessionState.CLOSED
        if audio is not None and audio.stop_reason:
            return SessionState.DEGRADED
        if self._video.waiting:
            return SessionState.WAITING
        if self._video.geometry is None:
            return SessionState.DEGRADED
        return SessionState.OPEN

    def _voice_lost(self, audio: AudioMeasurement | None) -> str:
        """Why the panel's voice stopped reaching the browser, or empty if it has not."""
        return "" if audio is None else audio.stop_reason

    def _video_flow(self) -> VideoFlow | None:
        """What the picture is doing, or None once there is no picture to report."""
        geometry = self._video.geometry
        if geometry is None:
            return None
        return VideoFlow(
            width=geometry.width,
            height=geometry.height,
            packets_sent=self._video.sent,
            packets_dropped=self._video.dropped,
        )

    def _audio_flow(self, audio: AudioMeasurement | None) -> AudioFlow | None:
        """What the voice is doing, counted at the doorphone's own clock."""
        if audio is None:
            return None
        return AudioFlow(
            from_doorphone=audio.received,
            to_browser=audio.packets_delivered,
            to_doorphone=audio.supplied,
            silence_sent=audio.underruns,
            partial_from_doorphone=audio.partial_frames,
            dropped_from_doorphone=audio.dropped_downlink,
            dropped_to_doorphone=audio.dropped_uplink,
            max_callback_ms=audio.max_callback_ms,
            budget_ms=audio.budget_ms,
        )

    # -- helpers ----------------------------------------------------------

    async def _stop_uplink(self) -> None:
        task, self._uplink = self._uplink, None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    def _require_bridge(self) -> AudioBridge:
        if self._bridge is None:
            raise AudioFormatMismatchError("the audio bridge was never attached")
        return self._bridge
