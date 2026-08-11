"""G.711 A-law on the WebRTC side: what is pinned, and the one table.

The panel sends A-law, read off pjsua's own stream dump on a live call as
``TX pt=8``. Payload type 8 is PCMA, so PCMA is what the browser leg is pinned
to and the whole path runs at one rate, one channel and one frame length: no
resampler, no channel mix, no second lossy generation.

The SDK's tap is a port on the conference bridge, and a bridge deals in linear
16 bit PCM whatever the codec on the wire was. pjmedia expands the panel's A-law
before a byte reaches the sink, so the downlink folds those samples back here and
hands aiortc a packet, which the encoder's ``pack`` puts on the wire untouched.
The fold is exact rather than approximate: what pjmedia produced are A-law
reconstruction points, and companding a reconstruction point returns the byte it
was decoded from, verified over all 256 of them against ffmpeg's own decoder.
The result depends on the top 13 bits only, so 8192 entries cover every sample.
"""

import array
from fractions import Fraction

from aiortc import RTCPeerConnection, RTCRtpSender
from aiortc.rtcrtpparameters import RTCRtpCodecCapability

from urmet_gateway.domain.errors import PcmaUnavailableError

# The RTP clock every G.711 payload runs on, and the timebase aiortc converts a
# handed-over packet from.
PCMA_TIME_BASE = Fraction(1, 8000)
PCMA_MIME = "audio/PCMA"

# The segment ends of the A-law encoding, in the form the specification defines
# and the form pjmedia compands with, so both ends agree byte for byte.
_SEGMENT_ENDS = (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF)
_SEGMENTS = 8
_TABLE_SIZE = 8192
_SIGN_SPLIT = 4096
_INDEX_MASK = 0x1FFF
_INDEX_SHIFT = 3
_BYTES_PER_SAMPLE = 2


def _companded(value: int) -> int:
    """One 13 bit sample as its A-law byte."""
    if value >= 0:
        mask = 0xD5
    else:
        mask = 0x55
        value = -value - 1
    segment = next((i for i, end in enumerate(_SEGMENT_ENDS) if value <= end), _SEGMENTS)
    if segment >= _SEGMENTS:
        return 0x7F ^ mask
    low = (value >> 1) & 0x0F if segment < 2 else (value >> segment) & 0x0F
    return ((segment << 4) | low) ^ mask


_ALAW_TABLE = bytes(
    _companded(i - _TABLE_SIZE if i >= _SIGN_SPLIT else i) for i in range(_TABLE_SIZE)
)


def to_alaw(pcm: bytes) -> bytes:
    """Fold linear 16 bit host-order samples back to the A-law bytes they were.

    Whole samples only. The trailing odd byte of a frame carrying half of one is
    dropped rather than completed with a zero: a zero would put a sample on the
    wire that nobody produced, and there is nothing here that could know what it
    should be. What is dropped is under 125 microseconds of speech, below what a
    listener can hear, while the exception it replaces would end the browser's
    audio track for the rest of the call. The caller compares the two lengths
    when it wants to know that it happened.
    """
    whole = len(pcm) - len(pcm) % _BYTES_PER_SAMPLE
    samples = array.array("h")
    samples.frombytes(memoryview(pcm)[:whole])
    return bytes(_ALAW_TABLE[(s >> _INDEX_SHIFT) & _INDEX_MASK] for s in samples)


def pin_pcma(pc: RTCPeerConnection) -> list[RTCRtpCodecCapability]:
    """Make PCMA the only audio codec offered, and say which ones those are.

    aiortc lists Opus first and negotiation takes the first both ends know, so a
    track handing over A-law payloads on an Opus line sends steadily and delivers
    nothing. The transceivers have to exist and the preference has to be in place
    before ``setRemoteDescription``, where aiortc settles the common codec list
    and never revisits it. So an answering connection calls ``addTrack`` first,
    then this, then ``setRemoteDescription``.
    """
    codecs = [
        codec
        for codec in RTCRtpSender.getCapabilities("audio").codecs
        if codec.mimeType == PCMA_MIME
    ]
    if not codecs:
        raise PcmaUnavailableError(f"this aiortc build publishes no {PCMA_MIME} to pin")
    for transceiver in pc.getTransceivers():
        if transceiver.kind == "audio":
            transceiver.setCodecPreferences(codecs)
    return codecs
