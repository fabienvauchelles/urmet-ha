"""Scenario: the panel changes picture size, and the browser sees one stream.

An answered ring sends a much larger picture than an on-demand view, and the pj
recorder writes its geometry into a file header once. So a size change is not a
parameter to update: the recorder and the encoder are torn down and built again on
a new pipe (``VideoDownlink.restart``), while the call carries on.

What must not be rebuilt is the track. Its timeline is the only clock in the path,
and a restart that put a timestamp back in the past would leave every packet late,
stop ``recv`` awaiting, and starve the loop with no error and no output (trap 8).
That failure has no symptom to assert afterwards, so it is asserted directly, at the
downlink itself.

The last scenario covers the other track export, ``pin_h264``: the codec the panel
speaks is the only one left on the video line (trap 9).
"""

import av
from aiortc import RTCPeerConnection
from support import DEFAULT_FORMAT, FakeVideoTap, stand_in_encoder
from urmet_sdk import VideoFormat

from urmet_gateway.media.pipeline import VideoDownlink
from urmet_gateway.media.track import H264_MIME, RTX_MIME, VideoPacketTrack, pin_h264

RING_FORMAT = VideoFormat(width=656, height=656)


async def test_the_downlink_timeline_carries_across_a_rebuild() -> None:
    """The track outlives the pipeline, and its clock only ever moves forward."""
    downlink = VideoDownlink(FakeVideoTap())
    with stand_in_encoder(alive=True):
        try:
            await downlink.start()
            track = downlink.track
            first_pipe = downlink.pipe_path
            first_generation = downlink.generation
            before = await _through(track, b"before the rebuild")

            await downlink.restart()

            # The pipe and encoder are new, the generation moved, the track is not.
            assert downlink.pipe_path != first_pipe
            assert downlink.generation != first_generation
            assert downlink.track is track
            after = await _through(track, b"after the rebuild")
            assert after.pts > before.pts
            assert after.time_base == before.time_base
            assert bytes(after) == b"after the rebuild"
        finally:
            await downlink.aclose()

    # A track that has ended stays ended: a teardown does not follow a restart.
    assert track.readyState == "ended"


async def test_a_resize_rearms_the_tap_on_a_new_pipe() -> None:
    """The rebuild sequence a session owner runs: close, restart, arm on the new path.

    The recorder header fixes geometry, so the tap is armed again on a pipe of its
    own; the recorded budget carries the panel's new size, and the track is the same
    object throughout.
    """
    tap = FakeVideoTap(video_format=DEFAULT_FORMAT)
    downlink = VideoDownlink(tap)
    with stand_in_encoder(alive=True):
        try:
            await downlink.start()
            track = downlink.track
            first = await downlink.arm(downlink.generation)
            assert first == DEFAULT_FORMAT
            first_pipe, first_generation = tap.opens[-1]

            tap.video_format = RING_FORMAT
            await tap.close_video()
            await downlink.restart()
            second = await downlink.arm(downlink.generation)

            assert second == RING_FORMAT
            second_pipe, second_generation = tap.opens[-1]
            assert second_pipe != first_pipe
            assert second_generation != first_generation
            assert downlink.track is track
        finally:
            await downlink.aclose()


async def test_pin_h264_keeps_only_h264_and_its_repair() -> None:
    """The panel speaks H.264, and nothing else may stay on the video line (trap 9)."""
    pc = RTCPeerConnection()
    try:
        pc.addTransceiver("video", direction="sendonly")
        kept = pin_h264(pc)
        mimes = {codec.mimeType for codec in kept}
        assert mimes <= {H264_MIME, RTX_MIME}
        assert H264_MIME in mimes
    finally:
        await pc.close()


async def _through(track: VideoPacketTrack, payload: bytes) -> av.Packet:
    """Hand one packet to the track the way the demuxer does, and take it back."""
    track.submit(av.Packet(payload))
    return await track.recv()
