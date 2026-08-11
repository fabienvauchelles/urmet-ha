"""Repairs issues and the one fixable flow (DESIGN 6.7, 12).

Three issues, keyed per config entry so two panels never collide:

- ``unconfirmed_release``: a ``registration`` event with ``released: false`` (a SIP
  binding that could not be released, DESIGN 5.6). Not fixable.
- ``auth_failure``: a ``registration`` event that came back not registered with a
  401 or 403, i.e. the cloud credentials were rejected (DESIGN 12 risk 11). Not
  fixable: the credentials live in the add-on options, not in a HA reauth flow.
- ``calls_not_routed``: three consecutive 503 while registered, the Route trap
  where registration is healthy and every call is refused before routing (DESIGN
  5.8). Fixable: the flow re-reads the gateway configuration by reloading the entry.

The registration issues are driven by the gateway event stream; the 503 count is
fed by the WebSocket offer proxy through :func:`note_offer_status`, because a bare
503 is a command result, not an event.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .coordinator import UrmetConfigEntry
from .events import GatewayEvent, RegistrationEvent, StateEvent

ISSUE_UNCONFIRMED_RELEASE = "unconfirmed_release"
ISSUE_AUTH_FAILURE = "auth_failure"
ISSUE_CALLS_NOT_ROUTED = "calls_not_routed"

AUTH_STATUS_CODES = frozenset({401, 403})
ROUTE_503_THRESHOLD = 3
_SUCCESS_STATUSES = frozenset({200, 201, 204})


def _issue_id(base: str, entry_id: str) -> str:
    return f"{base}_{entry_id}"


class UrmetIssueMonitor:
    """Raises and clears the three repairs issues for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._registered = False
        self._consecutive_503 = 0

    @callback
    def handle_event(self, event: GatewayEvent) -> None:
        """React to a gateway event (registration health, DESIGN 5.3)."""
        if isinstance(event, StateEvent):
            self._registered = event.state.registered
        elif isinstance(event, RegistrationEvent):
            self._on_registration(event)

    @callback
    def _on_registration(self, event: RegistrationEvent) -> None:
        self._registered = event.registered
        if event.registered:
            self._clear(ISSUE_UNCONFIRMED_RELEASE)
            self._clear(ISSUE_AUTH_FAILURE)
            return
        if event.released is False:
            self._raise(ISSUE_UNCONFIRMED_RELEASE, ir.IssueSeverity.WARNING, fixable=False)
        if event.status_code in AUTH_STATUS_CODES:
            self._raise(ISSUE_AUTH_FAILURE, ir.IssueSeverity.ERROR, fixable=False)

    @callback
    def note_offer_status(self, status: int) -> None:
        """Count a WebRTC offer result: three 503 in a row is the Route trap."""
        if status == 503:
            if not self._registered:
                return
            self._consecutive_503 += 1
            if self._consecutive_503 >= ROUTE_503_THRESHOLD:
                self._raise(ISSUE_CALLS_NOT_ROUTED, ir.IssueSeverity.ERROR, fixable=True)
        elif status in _SUCCESS_STATUSES:
            self._consecutive_503 = 0
            self._clear(ISSUE_CALLS_NOT_ROUTED)
        else:
            self._consecutive_503 = 0

    def _raise(self, base: str, severity: ir.IssueSeverity, *, fixable: bool) -> None:
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            _issue_id(base, self._entry_id),
            is_fixable=fixable,
            severity=severity,
            translation_key=base,
            data={"entry_id": self._entry_id} if fixable else None,
        )

    def _clear(self, base: str) -> None:
        ir.async_delete_issue(self._hass, DOMAIN, _issue_id(base, self._entry_id))


@callback
def async_attach_issue_monitor(entry: UrmetConfigEntry) -> CALLBACK_TYPE:
    """Subscribe a per-entry issue monitor; return its unsubscribe callback."""
    data = entry.runtime_data
    monitor = UrmetIssueMonitor(data.coordinator.hass, entry.entry_id)
    data.issue_monitor = monitor
    unsub_events = data.client.add_event_listener(monitor.handle_event)

    @callback
    def _detach() -> None:
        unsub_events()
        data.issue_monitor = None

    return _detach


@callback
def note_offer_status(entry: UrmetConfigEntry, status: int) -> None:
    """Report a WebRTC offer HTTP status to the entry's issue monitor."""
    monitor = entry.runtime_data.issue_monitor
    if monitor is not None:
        monitor.note_offer_status(status)


class CallsNotRoutedRepairFlow(RepairsFlow):
    """Fix ``calls_not_routed`` by reloading the entry (re-reads the gateway)."""

    def __init__(self, data: dict[str, Any] | None) -> None:
        self._entry_id = (data or {}).get("entry_id")

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> FlowResult:
        if user_input is not None:
            if isinstance(self._entry_id, str):
                await self.hass.config_entries.async_reload(self._entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Build the fix flow. Only ``calls_not_routed`` is fixable (DESIGN 6.7)."""
    return CallsNotRoutedRepairFlow(data)
