"""The gateway's own typed errors, and the SDK errors it re-exports.

The SDK's errors are re-exported here rather than re-wrapped, so a use case
raises ``OpenNotAcknowledgedError`` unchanged and the HTTP layer maps it by type
without unwrapping anything. The gateway-owned errors below cover the failures
the SDK has no word for: a call id the interface named that no dialog carries, an
offer that arrived with no media to bridge, a process built with no tap at all, a
malformed request body, and a voice path the tap and the bridge cannot agree on.
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


class UnknownCallError(GatewayError, LookupError):
    """No dialog the gateway is watching carries that call id."""


class NoStreamingCallError(GatewayError):
    """No call is carrying media, so there is nothing for a browser to join."""


class MediaUnavailableError(GatewayError):
    """This gateway holds no media tap, so no call can be bridged into a browser."""


class MalformedBodyError(GatewayError):
    """A request body was not the documented JSON object; the detail names the field."""


class AudioFormatMismatchError(GatewayError):
    """The tap and the browser bridge disagree on the voice format, so it is refused."""


__all__ = [
    "AudioFormatMismatchError",
    "CallError",
    "GatewayError",
    "MalformedBodyError",
    "MediaUnavailableError",
    "NoStreamingCallError",
    "NoVideoOfferedError",
    "NotRegisteredError",
    "OpenNotAcknowledgedError",
    "RegistrationError",
    "SipError",
    "UnknownCallError",
    "UrmetError",
]
