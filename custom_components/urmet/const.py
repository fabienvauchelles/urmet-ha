"""Constants for the Urmet doorphone integration.

The integration talks HTTP and WebSocket to the ``urmet-gateway`` add-on. Every
value here is part of the contract with that add-on (DESIGN 5.2, 5.3) or the
Home Assistant entity model (DESIGN 6.3); nothing is a tunable a user should
change without also changing the add-on.
"""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "urmet"
LOGGER: Final = logging.getLogger(__package__)

# --- Config entry data keys ------------------------------------------------
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
# 172.30.32.1 is the Supervisor bridge gateway, which is how a Core container
# reaches a ``host_network: true`` add-on (DESIGN 6.1).
DEFAULT_HOST: Final = "172.30.32.1"
DEFAULT_PORT: Final = 8099

# --- Options keys ----------------------------------------------------------
CONF_RING_COALESCE: Final = "ring_coalesce_s"
DEFAULT_RING_COALESCE: Final = 5

# --- Domain vocabulary (DESIGN 5.2, 6.5) -----------------------------------
# The two actuators and who initiated an open. Shared by the command layer and
# the read-only entity platforms, so they live here rather than in the command
# module the read path would otherwise depend on. The call and session states
# are the wire vocabulary and live with their models, in ``models.py``.
ACTUATOR_DOOR: Final = "door"
ACTUATOR_GATE: Final = "gate"

ORIGIN_CARD: Final = "card"
ORIGIN_SERVICE: Final = "service"
ORIGIN_NOTIFICATION: Final = "notification"
DEFAULT_ORIGIN: Final = ORIGIN_SERVICE

# --- Device identity (DESIGN 6.3) ------------------------------------------
MANUFACTURER: Final = "Urmet"
MODEL: Final = "Mini Note 1722/958 (2Voice)"
DEVICE_NAME: Final = "Portier"
# The display name is "Jardin Avant" while the area id on the box is "jardin";
# suggested_area matches on the display name (DESIGN 6.3).
SUGGESTED_AREA: Final = "Jardin Avant"

# --- Gateway HTTP / WebSocket paths (DESIGN 5.2, 5.3) ----------------------
HEALTH_PATH: Final = "/api/health"
STATE_PATH: Final = "/api/state"
EVENTS_PATH: Final = "/api/events"

# --- Event-stream reconnect (DESIGN 6.2) -----------------------------------
# 1, 2, 4, 8, 15 s, last value repeating, with +/- 25 % jitter. The client logs
# once per step, never once per attempt, so a long outage does not spam the log.
BACKOFF_SCHEDULE_S: Final = (1.0, 2.0, 4.0, 8.0, 15.0)
BACKOFF_JITTER: Final = 0.25
WS_HEARTBEAT_S: Final = 30.0
REQUEST_TIMEOUT_S: Final = 10.0

# --- Event-stream types (DESIGN 5.3) ---------------------------------------
EVENT_STATE: Final = "state"
EVENT_RING: Final = "ring"
EVENT_CALL: Final = "call"
EVENT_OPEN: Final = "open"
EVENT_REGISTRATION: Final = "registration"
EVENT_WEBRTC: Final = "webrtc"

# --- Entity unique_id suffixes (DESIGN 6.3) --------------------------------
# WP8 builds every entity as f"{mac}_{suffix}"; the suffixes live here so the
# entity platforms and any test that asserts a unique_id share one source.
KEY_DOORBELL: Final = "doorbell"
KEY_ACTUATOR: Final = "actuator"
KEY_OPEN_DOOR: Final = "open_door"
KEY_OPEN_GATE: Final = "open_gate"
KEY_LOOK: Final = "look"
KEY_ANSWER: Final = "answer"
KEY_HANGUP: Final = "hangup"
KEY_MIC: Final = "mic"
KEY_REGISTERED: Final = "registered"
KEY_CALL_ACTIVE: Final = "call_active"
KEY_CALL_STATE: Final = "call_state"
KEY_LAST_RING: Final = "last_ring"
KEY_RING_TOTAL: Final = "ring_total"
KEY_DOOR_TOTAL: Final = "door_total"
KEY_GATE_TOTAL: Final = "gate_total"
KEY_REG_STATUS: Final = "reg_status"
KEY_LAST_ERROR: Final = "last_error"
