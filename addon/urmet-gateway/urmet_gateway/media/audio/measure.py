"""What a caller may read back about one call's voice, as one snapshot.

Two readings, taken together so they cannot disagree. What the clock thread did
says how much audio crossed the boundary and what that cost it. What the downlink
track did says how much of it aiortc was actually handed, and why it stopped
being handed anything if it stopped. Only the pair distinguishes a call nobody is
speaking on from a call whose sender died.
"""

from pydantic import BaseModel, ConfigDict

from urmet_gateway.media.audio.bridge import AudioBridge

# The working ceiling one callback is held to, as a fraction of the frame
# interval. The hard limit is the interval itself, at which the bridge misses a
# frame; a tenth of it is the budget that leaves the other ports their share.
BUDGET_FRACTION = 0.1

_MS_PER_SECOND = 1000


class AudioMeasurement(BaseModel):
    """What the clock thread really cost, and how much audio was lost."""

    model_config = ConfigDict(frozen=True)

    received: int
    supplied: int
    underruns: int
    dropped_downlink: int
    dropped_uplink: int
    unreachable_loop: int
    packets_delivered: int
    partial_frames: int
    stop_reason: str
    max_callback_ms: float
    p99_callback_ms: float
    budget_ms: float


def measure_audio_bridge(bridge: AudioBridge) -> AudioMeasurement:
    """Read the bridge's counters and timings, so a live test can assert them.

    ``max_callback_ms`` is over the whole run and ``p99_callback_ms`` over the
    last ``TIMING_WINDOW`` callbacks, which makes one slow first frame visible
    without letting it hide a run that went bad later. ``underruns`` counts the
    intervals the doorphone was sent silence because the browser had supplied
    nothing, so a muted page reports one per frame, which is correct.

    ``packets_delivered`` is taken at the hand-over to aiortc and not at the
    clock thread, so it is the one number that goes still when the browser stops
    hearing the panel. ``stop_reason`` says why it went still, and is empty for
    as long as the downlink track is live. ``partial_frames`` counts the frames
    the panel sent that were not whole samples, carried rather than refused.
    """
    interval_ms = float(bridge.audio_format.frame_time_ms)
    return AudioMeasurement(
        received=bridge.received,
        supplied=bridge.supplied,
        underruns=bridge.underruns,
        dropped_downlink=bridge.dropped_downlink,
        dropped_uplink=bridge.dropped_uplink,
        unreachable_loop=bridge.unreachable_loop,
        packets_delivered=bridge.packets_delivered,
        partial_frames=bridge.partial_frames,
        stop_reason=bridge.stop_reason,
        max_callback_ms=bridge.timings.max_s * _MS_PER_SECOND,
        p99_callback_ms=bridge.timings.p99_s() * _MS_PER_SECOND,
        budget_ms=interval_ms * BUDGET_FRACTION,
    )
