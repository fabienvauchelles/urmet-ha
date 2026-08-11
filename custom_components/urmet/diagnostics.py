"""Config-entry diagnostics (DESIGN 6.7).

The dump is the entry data and options plus the gateway's own
``GET /api/diagnostics`` body. No credential ever reaches the integration: the
cloud password lives in the add-on options and is never echoed, so redaction
covers ``host`` only, for tidiness, and this module says so rather than
pretending to redact a secret it does not receive.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .client import GatewayClient, GatewayConnectionError
from .const import CONF_HOST
from .coordinator import UrmetConfigEntry

DIAGNOSTICS_PATH = "/api/diagnostics"
TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UrmetConfigEntry
) -> dict[str, Any]:
    """Return the redacted entry configuration and the gateway diagnostics."""
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "gateway": await _gateway_diagnostics(entry.runtime_data.client),
    }


async def _gateway_diagnostics(client: GatewayClient) -> dict[str, Any]:
    """Fetch ``GET /api/diagnostics``; report the reason on any failure."""
    try:
        response = await client.async_request("GET", DIAGNOSTICS_PATH)
    except GatewayConnectionError as err:
        return {"error": str(err)}
    if response.status != 200:
        return {"error": f"gateway returned {response.status} for {DIAGNOSTICS_PATH}"}
    return response.body
