"""Config-entry diagnostics golden-file scenario (DESIGN 6.7)."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from webrtc_gateway import WebrtcGateway
from wp9_support import gateway, setup_entry  # noqa: F401

from custom_components.urmet.diagnostics import async_get_config_entry_diagnostics

_GOLDEN = Path(__file__).parent / "diagnostics_golden.json"


async def test_diagnostics_matches_golden(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
) -> None:
    entry = await setup_entry(hass, gateway)

    dump = await async_get_config_entry_diagnostics(hass, entry)

    expected = json.loads(_GOLDEN.read_text())
    # The loopback port is chosen at runtime and is not redacted (DESIGN 6.7 redacts
    # host only); normalise it to the golden sentinel before comparing.
    assert dump["entry"]["data"]["port"] == gateway.port
    expected["entry"]["data"]["port"] = gateway.port

    assert dump == expected


async def test_diagnostics_host_is_redacted(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
) -> None:
    entry = await setup_entry(hass, gateway)

    dump = await async_get_config_entry_diagnostics(hass, entry)

    assert dump["entry"]["data"]["host"] == "**REDACTED**"
