"""The push coordinator fed by the gateway's event stream (DESIGN 6.2).

``UrmetCoordinator`` is a push ``DataUpdateCoordinator`` whose data is the latest
``StateView``: it never polls (``update_interval`` is ``None``) and is fed by the
client's ``state`` events. The first ``GET /api/state`` runs through
``async_config_entry_first_refresh`` so a cold gateway raises
``ConfigEntryNotReady`` and Home Assistant's own retry does the waiting. The
transport it drives lives in ``client.py``; this module is only the glue between
that client and Home Assistant's coordinator.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import GatewayClient, GatewayConnectionError
from .const import DOMAIN, LOGGER
from .events import GatewayEvent, StateEvent
from .models import StateView

if TYPE_CHECKING:
    # repairs imports this module for the entry type, so the monitor it owns is
    # named here for typing only. The annotations are lazy, so nothing imports
    # back at runtime and there is no cycle.
    from .repairs import UrmetIssueMonitor


class UrmetCoordinator(DataUpdateCoordinator[StateView]):
    """Push coordinator fed by the gateway's ``state`` events (DESIGN 6.2)."""

    def __init__(self, hass: HomeAssistant, entry: UrmetConfigEntry, client: GatewayClient) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=None)
        self.client = client
        self._unsubs: list[Callable[[], None]] = [
            client.add_event_listener(self._handle_event),
            client.add_connection_listener(self._handle_connection),
        ]

    async def _async_update_data(self) -> StateView:
        try:
            return await self.client.async_get_state()
        except GatewayConnectionError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def _handle_event(self, event: GatewayEvent) -> None:
        if isinstance(event, StateEvent):
            self.async_set_updated_data(event.state)

    @callback
    def _handle_connection(self, connected: bool) -> None:
        if not connected and self.last_update_success:
            self.async_set_update_error(GatewayConnectionError("gateway event stream disconnected"))

    @callback
    def async_release(self) -> None:
        """Drop the client listeners this coordinator registered."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()


@dataclass(frozen=True, slots=True)
class PendingOpen:
    """What is known about the open in flight: its source, and who asked for it.

    ``context`` carries the Home Assistant user behind the press or the service
    call, so the event entity can attribute the open to a person in the logbook.
    It is ``None`` when the caller was not a user.
    """

    origin: str
    context: Context | None


@dataclass
class UrmetRuntimeData:
    """Stored on ``entry.runtime_data``: everything one doorphone owns (DESIGN 6.2).

    ``pending_open`` and ``issue_monitor`` are per-entry state, so they live here
    rather than in a global ``hass.data`` map keyed by entry id: unloading the
    entry drops them with it, and two panels can never read each other's.
    """

    client: GatewayClient
    coordinator: UrmetCoordinator
    pending_open: PendingOpen | None = None
    issue_monitor: UrmetIssueMonitor | None = None


type UrmetConfigEntry = ConfigEntry[UrmetRuntimeData]
