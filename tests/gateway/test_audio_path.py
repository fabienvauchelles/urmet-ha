"""The audio path, end to end, driven through the SDK doubles and real ffmpeg.

Full-scenario, through the public surface: the bridge is attached to
``FakeMediaTap`` exactly as the SDK would attach it, and the fake plays pjmedia's
clock thread against it from a thread of its own. Nothing here imports pjsua2 or
opens the network. The one external process is ffmpeg, spawned as a codec double
to prove the A-law fold is not merely self-consistent but agrees with the decoder
aiortc uses at the far end.
"""

import asyncio
import shutil
import subprocess
from collections import deque

import av
import pytest
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
from urmet_sdk import AudioFormat
from urmet_sdk.testing import FakeCall, FakeMediaTap

from urmet_gateway.media.audio.bridge import BACKLOG_FRAMES, AudioBridge
from urmet_gateway.media.audio.g711 import to_alaw
from urmet_gateway.media.audio.measure import measure_audio_bridge
from urmet_gateway.media.audio.tracks import BrowserAudioPump, DoorphoneAudioTrack

TAP_FORMAT = AudioFormat(clock_rate=8000, channels=1, frame_time_ms=20, bits_per_sample=16)
FRAME_BYTES = TAP_FORMAT.frame_bytes  # 320: 160 samples of s16 mono at 8 kHz, 20 ms
ALAW_PER_FRAME = FRAME_BYTES // 2  # one A-law byte per 16-bit sample
FRAMES_PER_SECOND = 50
_FFMPEG = shutil.which("ffmpeg")


def _pcm_frame(seed: int, size: int = FRAME_BYTES) -> bytes:
    """A deterministic 20 ms PCM frame that is not silence, so drops show."""
    return bytes((seed * 7 + i * 3) % 256 for i in range(size))


def _audio_frame(pcm: bytes) -> av.AudioFrame:
    """One decoded s16 mono 8 kHz frame, as aiortc hands the uplink pump."""
    frame = av.AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
    frame.sample_rate = TAP_FORMAT.clock_rate
    frame.planes[0].update(pcm)
    return frame


class _DecodedTrack(MediaStreamTrack):
    """A browser uplink track that yields decoded frames, then ends."""

    kind = "audio"

    def __init__(self, frames: list[av.AudioFrame]) -> None:
        super().__init__()
        self._frames = deque(frames)

    async def recv(self) -> av.AudioFrame:
        if not self._frames:
            raise MediaStreamError("the browser track ended")
        return self._frames.popleft()


def _decode_alaw_with_ffmpeg(alaw: bytes) -> bytes:
    """Decode A-law bytes to their s16 reconstruction points, via ffmpeg."""
    assert _FFMPEG is not None
    result = subprocess.run(
        [
            _FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "alaw",
            "-ar",
            "8000",
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-ar",
            "8000",
            "-ac",
            "1",
            "pipe:1",
        ],
        input=alaw,
        capture_output=True,
        check=True,
    )
    return result.stdout


async def test_fifty_frames_each_way_through_the_fake_tap() -> None:
    """A second of audio both ways: nothing lost, exact folds, callbacks in budget."""
    bridge = AudioBridge(TAP_FORMAT)
    tap = FakeMediaTap()
    call = FakeCall("call-two-way")
    assert tap.attach_audio_tap(call, bridge) == TAP_FORMAT

    track = DoorphoneAudioTrack(bridge)
    downlink = [_pcm_frame(i) for i in range(FRAMES_PER_SECOND)]
    uplink = [_pcm_frame(500 + i) for i in range(FRAMES_PER_SECOND)]

    delivered: list[av.Packet] = []

    async def drain() -> None:
        while len(delivered) < FRAMES_PER_SECOND:
            delivered.append(await track.recv())

    reader = asyncio.create_task(drain())

    supplied: list[bytes] = []
    for down, up in zip(downlink, uplink, strict=True):
        bridge.push_uplink(up)
        supplied += await asyncio.to_thread(tap.run_audio, call, [down])
        await asyncio.sleep(0)
    await asyncio.wait_for(reader, timeout=5.0)

    # Downlink: every frame reached aiortc, folded to A-law, in order, once each.
    assert bridge.received == FRAMES_PER_SECOND
    assert bridge.dropped_downlink == 0
    assert bridge.packets_delivered == FRAMES_PER_SECOND
    assert [bytes(packet) for packet in delivered] == [to_alaw(down) for down in downlink]
    assert [packet.pts for packet in delivered] == [
        i * ALAW_PER_FRAME for i in range(FRAMES_PER_SECOND)
    ]

    # Uplink: every frame the browser supplied was handed to the stack, unchanged.
    assert supplied == uplink
    assert bridge.supplied == FRAMES_PER_SECOND
    assert bridge.underruns == 0
    assert bridge.dropped_uplink == 0
    assert bridge.unreachable_loop == 0

    # The clock thread never came near the frame it would have missed a frame at.
    reading = measure_audio_bridge(bridge)
    assert reading.budget_ms == 2.0
    assert reading.max_callback_ms < reading.budget_ms
    assert reading.stop_reason == ""


async def test_clock_thread_stays_bounded_and_fast_under_pressure() -> None:
    """Handed frames faster than anyone drains, the bridge drops, never grows."""
    bridge = AudioBridge(TAP_FORMAT)
    tap = FakeMediaTap()
    call = FakeCall("call-flood")
    tap.attach_audio_tap(call, bridge)

    flood = FRAMES_PER_SECOND * 2  # 100 frames each way, no reader draining
    for i in range(flood):
        bridge.push_uplink(_pcm_frame(900 + i))
    supplied = await asyncio.to_thread(tap.run_audio, call, [_pcm_frame(i) for i in range(flood)])

    assert bridge.received == flood
    assert bridge.dropped_downlink == flood - BACKLOG_FRAMES
    # Only the last BACKLOG_FRAMES survived priming; the rest are silence.
    assert len(supplied) == BACKLOG_FRAMES
    assert bridge.supplied == BACKLOG_FRAMES
    assert bridge.underruns == flood - BACKLOG_FRAMES
    assert bridge.dropped_uplink == flood - BACKLOG_FRAMES

    reading = measure_audio_bridge(bridge)
    assert reading.max_callback_ms < reading.budget_ms


@pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg is required to decode A-law")
def test_alaw_fold_is_exact_over_every_reconstruction_point() -> None:
    """Companding each of the 256 A-law reconstruction points returns its byte."""
    every_byte = bytes(range(256))
    reconstruction_points = _decode_alaw_with_ffmpeg(every_byte)
    assert len(reconstruction_points) == 256 * 2

    # In bulk, and point by point, so a single wrong byte names itself.
    assert to_alaw(reconstruction_points) == every_byte
    for value in range(256):
        sample = reconstruction_points[value * 2 : value * 2 + 2]
        assert to_alaw(sample) == bytes([value]), f"A-law byte {value} did not round-trip"


async def test_browser_pump_recuts_decoded_frames_into_tap_frames() -> None:
    """Uplink frames of any size are re-cut to the tap's frame, converting nothing."""
    bridge = AudioBridge(TAP_FORMAT)
    payloads = [_pcm_frame(i, size=200) for i in range(8)]  # 1600 bytes = five tap frames
    pump = BrowserAudioPump(bridge, _DecodedTrack([_audio_frame(p) for p in payloads]))

    await pump.run()

    expected_frames = (len(payloads) * 200) // FRAME_BYTES
    assert pump.frames == expected_frames
    reassembled = b"".join(bridge.next_frame() or b"" for _ in range(expected_frames))
    assert reassembled == b"".join(payloads)[: expected_frames * FRAME_BYTES]


async def test_partial_and_empty_downlink_frames_are_carried_not_refused() -> None:
    """A short frame is folded to what it carries; an empty one is passed over."""
    bridge = AudioBridge(TAP_FORMAT)
    tap = FakeMediaTap()
    call = FakeCall("call-partial")
    tap.attach_audio_tap(call, bridge)
    track = DoorphoneAudioTrack(bridge)

    partial = _pcm_frame(1, size=FRAME_BYTES + 1)  # odd length: one dangling half-sample
    whole = _pcm_frame(2)
    await asyncio.to_thread(tap.run_audio, call, [b"", partial, whole])

    first = await track.recv()  # the empty frame is skipped inside this pull
    second = await track.recv()

    assert bytes(first) == to_alaw(partial)
    assert len(bytes(first)) == FRAME_BYTES // 2  # the trailing half-sample was dropped
    assert bytes(second) == to_alaw(whole)
    assert bridge.received == 3
    assert bridge.partial_frames == 1
    assert bridge.packets_delivered == 2
