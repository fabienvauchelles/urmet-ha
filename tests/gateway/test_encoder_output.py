"""The one scenario that runs the real ffmpeg, because ffmpeg is what it tests.

Every other scenario stands a coreutils program in for the encoder: a suite that
spawned ffmpeg would be measuring ffmpeg. This one has no such option. ``encoder_argv``
chooses the container, and the container decides whether the H.264 leaving it carries
Annex B start codes or length-prefixed NAL units. aiortc's packetiser splits on start
codes, so the wrong container makes it find nothing to pack: packets go out, the
counters climb, nothing raises, and the browser decodes not one frame (trap 7).
Asserting the argument list instead would only restate the code; the property is in
the bytes.
"""

import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import av
import pytest

from urmet_gateway.media.encoder import encoder_argv

# The four-byte Annex B prefix x264 puts in front of a parameter set and a keyframe.
ANNEX_B_START = b"\x00\x00\x00\x01"
SOURCE_FRAMES = 30
SOURCE_SIZE = (320, 240)
ENCODE_TIMEOUT_S = 30

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="this scenario judges ffmpeg's own output, so it needs ffmpeg",
)


@pytest.fixture
def uncompressed_avi(tmp_path: Path) -> Path:
    """An uncompressed AVI shaped like the one the SDK's recorder writes."""
    path = tmp_path / "tap.avi"
    with av.open(str(path), "w", format="avi") as container:
        stream = container.add_stream("rawvideo", rate=15)
        stream.width, stream.height = SOURCE_SIZE
        stream.pix_fmt = "yuv420p"
        stream.time_base = Fraction(1, 15)
        for index in range(SOURCE_FRAMES):
            frame = av.VideoFrame(*SOURCE_SIZE, "yuv420p")
            # A moving value, so the encoder cannot collapse the run into one frame.
            for plane in frame.planes:
                plane.update(bytes([(index * 8) % 256]) * plane.buffer_size)
            frame.pts = index
            frame.time_base = stream.time_base
            container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    return path


def _encode(source: Path) -> bytes:
    """Run the real invocation over ``source`` and return what it wrote."""
    finished = subprocess.run(
        encoder_argv(source), capture_output=True, timeout=ENCODE_TIMEOUT_S, check=False
    )
    assert finished.returncode == 0, finished.stderr.decode("utf-8", "replace")
    assert finished.stdout, "the encoder produced nothing at all"
    return finished.stdout


def test_the_encoder_emits_annex_b_that_a_decoder_accepts(uncompressed_avi: Path) -> None:
    written = uncompressed_avi.parent / "encoded.ts"
    written.write_bytes(_encode(uncompressed_avi))
    with av.open(str(written)) as container:
        stream = container.streams.video[0]
        assert stream.codec_context.name == "h264"
        packets = [packet for packet in container.demux(stream) if packet.pts is not None]

    assert packets, "nothing demuxed out of the encoder's own output"
    # The property the whole video path rests on. A container that stored NAL units
    # length-prefixed would fail here, and would fail nowhere else.
    assert bytes(packets[0])[:4] == ANNEX_B_START, (
        "the first packet does not begin with an Annex B start code, so aiortc's "
        "H.264 packetiser would find nothing to pack"
    )
    # force_key_frames makes the first frame an IDR, so a browser at stream start
    # waits no GOP (DESIGN 3.3): the very first packet is a keyframe.
    assert packets[0].is_keyframe, "the first encoded packet is not a keyframe"

    with av.open(str(written)) as container:
        decoded = list(container.decode(video=0))
    assert len(decoded) >= SOURCE_FRAMES // 2, f"only {len(decoded)} frames survived"
    assert (decoded[0].width, decoded[0].height) == SOURCE_SIZE


def test_the_encoder_stays_on_a_profile_a_browser_will_take(uncompressed_avi: Path) -> None:
    """Baseline and no B frames, both promises to the far end (in order, decodable)."""
    written = uncompressed_avi.parent / "profile.ts"
    written.write_bytes(_encode(uncompressed_avi))
    probed = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "error",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=profile,has_b_frames",
            "-of",
            "default=nw=1",
            str(written),
        ],
        capture_output=True,
        text=True,
        timeout=ENCODE_TIMEOUT_S,
        check=True,
    ).stdout
    assert "profile=Constrained Baseline" in probed or "profile=Baseline" in probed, probed
    assert "has_b_frames=0" in probed, probed
