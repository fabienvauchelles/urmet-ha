"""Repairs scenarios: three issues, each raised and cleared (DESIGN 6.7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from webrtc_gateway import WebrtcGateway
from wp9_support import gateway, setup_entry, wait_until  # noqa: F401

from custom_components.urmet.const import DOMAIN
from custom_components.urmet.repairs import (
    ISSUE_AUTH_FAILURE,
    ISSUE_CALLS_NOT_ROUTED,
    ISSUE_UNCONFIRMED_RELEASE,
    _issue_id,
)

OFFER_SDP = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=urmet-offer\r\n"

_COMPONENT = Path(__file__).resolve().parents[2] / "custom_components" / "urmet"
_STRING_FILES = (
    _COMPONENT / "strings.json",
    _COMPONENT / "translations" / "en.json",
    _COMPONENT / "translations" / "fr.json",
)


def test_repairs_issue_strings_present_and_mirrored() -> None:
    """Every issue repairs.py raises has strings in all three mirrored files."""
    keys = {ISSUE_UNCONFIRMED_RELEASE, ISSUE_AUTH_FAILURE, ISSUE_CALLS_NOT_ROUTED}
    for path in _STRING_FILES:
        issues = json.loads(path.read_text(encoding="utf-8")).get("issues", {})
        assert keys <= set(issues), f"{path.name} is missing issue strings: {keys - set(issues)}"
        for key in keys:
            assert issues[key].get("title"), f"{path.name}:{key} has no title"
            assert issues[key].get("description"), f"{path.name}:{key} has no description"
        # calls_not_routed is fixable, so it also needs the confirm-step strings.
        confirm = issues[ISSUE_CALLS_NOT_ROUTED]["fix_flow"]["step"]["confirm"]
        assert confirm.get("title") and confirm.get("description"), f"{path.name} confirm step"


def _registration(**fields: Any) -> dict[str, Any]:
    base = {
        "type": "registration",
        "at": None,
        "registered": False,
        "status_code": 0,
        "reason": "",
        "released": None,
    }
    base.update(fields)
    return base


async def test_unconfirmed_release_raised_and_cleared(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
) -> None:
    entry = await setup_entry(hass, gateway)
    registry = ir.async_get(hass)
    issue_id = _issue_id(ISSUE_UNCONFIRMED_RELEASE, entry.entry_id)

    await gateway.push_event(_registration(registered=False, released=False))
    await wait_until(hass, lambda: registry.async_get_issue(DOMAIN, issue_id) is not None)

    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is False

    await gateway.push_event(_registration(registered=True, status_code=200, released=None))
    await wait_until(hass, lambda: registry.async_get_issue(DOMAIN, issue_id) is None)


async def test_auth_failure_raised_and_cleared(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
) -> None:
    entry = await setup_entry(hass, gateway)
    registry = ir.async_get(hass)
    issue_id = _issue_id(ISSUE_AUTH_FAILURE, entry.entry_id)

    await gateway.push_event(_registration(registered=False, status_code=403))
    await wait_until(hass, lambda: registry.async_get_issue(DOMAIN, issue_id) is not None)

    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is False

    await gateway.push_event(_registration(registered=True, status_code=200))
    await wait_until(hass, lambda: registry.async_get_issue(DOMAIN, issue_id) is None)


async def test_calls_not_routed_raised_and_cleared(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
    hass_ws_client: Any,
) -> None:
    gateway.offer_status = 503
    entry = await setup_entry(hass, gateway)
    registry = ir.async_get(hass)
    issue_id = _issue_id(ISSUE_CALLS_NOT_ROUTED, entry.entry_id)

    # The monitor learns it is registered from the initial state event.
    await gateway.push_event(_registration(registered=True, status_code=200))
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    for msg_id in range(20, 23):  # three consecutive 503 (DESIGN 5.8)
        await client.send_json(
            {
                "id": msg_id,
                "type": "urmet/webrtc/offer",
                "entry_id": entry.entry_id,
                "sdp": OFFER_SDP,
            }
        )
        assert (await client.receive_json())["success"] is False

    await wait_until(hass, lambda: registry.async_get_issue(DOMAIN, issue_id) is not None)
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is True

    # A routed call clears it.
    gateway.offer_status = 201
    await client.send_json(
        {"id": 23, "type": "urmet/webrtc/offer", "entry_id": entry.entry_id, "sdp": OFFER_SDP}
    )
    assert (await client.receive_json())["success"] is True
    await wait_until(hass, lambda: registry.async_get_issue(DOMAIN, issue_id) is None)


async def test_calls_not_routed_fix_flow_reloads_entry(
    hass: HomeAssistant,
    gateway: WebrtcGateway,  # noqa: F811
) -> None:
    entry = await setup_entry(hass, gateway)
    from custom_components.urmet.repairs import async_create_fix_flow

    flow = await async_create_fix_flow(hass, "calls_not_routed", {"entry_id": entry.entry_id})
    flow.hass = hass

    form = await flow.async_step_init()
    assert form["type"] == "form"
    assert form["step_id"] == "confirm"

    result = await flow.async_step_confirm({})
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
