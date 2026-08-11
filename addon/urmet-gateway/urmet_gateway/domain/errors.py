"""Every error the gateway raises, and the SDK errors it re-exports.

The SDK's errors are re-exported here rather than re-wrapped, so a use case
raises ``OpenNotAcknowledgedError`` unchanged and the HTTP layer maps it by type
without unwrapping anything. The gateway-owned errors cover the failures the SDK
has no word for, and they all descend from ``GatewayError``: one root the HTTP
layer can name, and one module to read to know what this gateway can raise. Each
also keeps the built-in base a caller would reasonably catch it by
(``LookupError``, ``RuntimeError``, ``ValueError``), so nothing that caught one
before stops catching it now.
"""

from __future__ import annotations

from urmet_sdk import (
    CallError,
    NotRegisteredError,
    NoVideoOfferedError,
    OpenNotAcknowledgedError,
    RegistrationError,
    SipError,
    UrmetError,
)


class GatewayError(Exception):
    """Base for every error the gateway raises that the SDK has no word for."""


# --- Calls and sessions ----------------------------------------------------


class UnknownCallError(GatewayError, LookupError):
    """No dialog the gateway is watching carries that call id."""


class NoStreamingCallError(GatewayError):
    """No call is carrying media, so there is nothing for a browser to join."""


class MediaUnavailableError(GatewayError):
    """This gateway holds no media tap, so no call can be bridged into a browser."""


class MalformedBodyError(GatewayError):
    """A request body was not the documented JSON object; the detail names the field."""


# --- Adapters: the SIP thread, the holder and the event bus ----------------


class WorkerStoppedError(GatewayError, RuntimeError):
    """An SDK call was submitted after the worker had been shut down."""


class NoClientError(GatewayError, RuntimeError):
    """A command reached the holder before any client had been built."""


class EventBusClosedError(GatewayError, RuntimeError):
    """A subscription was asked for after the bus had been closed."""


# --- Media: the video pipeline and the two codec paths ---------------------


class DownlinkNotStartedError(GatewayError, RuntimeError):
    """The downlink was asked for something it only has once it has started."""


class StaleArmError(GatewayError, CallError):
    """An arm carrying a generation the pipeline has already moved past (trap 15)."""


class DownlinkNotDrainingError(GatewayError, CallError):
    """An arm attempted while no reader drains the pipe (trap 2)."""


class H264UnavailableError(GatewayError, RuntimeError):
    """This aiortc build publishes no H.264, so nothing could be pinned."""


class PcmaUnavailableError(GatewayError, RuntimeError):
    """This aiortc build publishes no PCMA, so nothing could be pinned."""


class AudioFormatMismatchError(GatewayError):
    """The tap and the browser bridge disagree on the voice format, so it is refused."""


class UplinkFormatError(GatewayError, ValueError):
    """The browser's track decoded to PCM the doorphone's tap cannot take."""


__all__ = [
    "AudioFormatMismatchError",
    "CallError",
    "DownlinkNotDrainingError",
    "DownlinkNotStartedError",
    "EventBusClosedError",
    "GatewayError",
    "H264UnavailableError",
    "MalformedBodyError",
    "MediaUnavailableError",
    "NoClientError",
    "NoStreamingCallError",
    "NoVideoOfferedError",
    "NotRegisteredError",
    "OpenNotAcknowledgedError",
    "PcmaUnavailableError",
    "RegistrationError",
    "SipError",
    "StaleArmError",
    "UnknownCallError",
    "UplinkFormatError",
    "UrmetError",
    "WorkerStoppedError",
]
