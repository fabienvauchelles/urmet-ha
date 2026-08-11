"""Measured constants the HTTP surface is built on, each with its measurement.

The media and tap constants live with the code that measured them, so there is
one source for each and no value can drift against another: ``MAX_TAP_BYTES`` in
``sip.tap``, the two watchdog budgets in ``media.pipeline``, the encoder argv in
``media.encoder``, the video queue depth in ``media.track`` and the event fan-out
capacity in ``usecases.events``. What this module owns is the surface WP5 adds:
where the gateway binds, and how the event stream paces itself. The asserts below
guard the ranges that bite if a value is ever edited by hand.
"""

from __future__ import annotations

from typing import Final

# The port the add-on exposes through ingress and on the host network. It must
# equal ``ingress_port`` in config.yaml (DESIGN 5.2, 5.9); the health route opens
# here before the SDK is up so a supervisor never reads the add-on as dead.
SERVER_PORT: Final = 8099

# The WebSocket ping cadence. Often enough to tell a client that vanished without
# a close from one that is merely quiet, and close the first; the read side of the
# stream has to run for the pong to be consumed (DESIGN 5.3).
WS_HEARTBEAT_S: Final = 30.0

# Small on purpose (DESIGN 5.3, urmet-web trap): what the writer does not buffer,
# the subscription queue does, and a queue that fills is exactly how a subscriber
# that stopped reading is noticed. A megabyte of socket buffer would hide it.
WS_WRITER_LIMIT: Final = 16 * 1024

assert 0.0 < WS_HEARTBEAT_S < 120.0
assert 1024 <= WS_WRITER_LIMIT <= 1 << 20
assert 1 <= SERVER_PORT <= 65535
