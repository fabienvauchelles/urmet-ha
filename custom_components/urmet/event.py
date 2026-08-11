"""Doorbell and actuator event entities (DESIGN 6.4, recon 13).

Two event entities, and no raw bus event carries the same information: firing
both is the documented anti-pattern (recon 11 section 6).

``event.portier_sonnette`` (device_class ``doorbell``) fires on the gateway
``ring`` event, coalescing a burst of presses into one event inside
``ring_coalesce_s`` so three presses do not raise three notifications
(DESIGN 5.4, 6.4).

``event.portier_ouverture`` fires on the gateway ``open`` event, the panel's own
acknowledgement. Its ``acknowledged`` attribute is the panel's answer, and a
``false`` there means the outcome is unknown, never "opened" (DESIGN 6.4). The
entity carries the origin the command layer stashed (card, service or
notification); it never mints a success the gateway did not report.
"""

from __future__ import annotations

import time

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTUATOR_DOOR,
    ACTUATOR_GATE,
    CONF_RING_COALESCE,
    DEFAULT_RING_COALESCE,
    KEY_ACTUATOR,
    KEY_DOORBELL,
)
from .coordinator import UrmetConfigEntry, UrmetCoordinator
from .entity import UrmetEntity
from .events import GatewayEvent, OpenEvent, RingEvent
from .services import take_open

EVENT_RING = "ring"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrmetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the doorbell and actuator event entities."""
    coordinator = entry.runtime_data.coordinator
    mac = str(entry.unique_id)
    async_add_entities(
        [DoorbellEvent(coordinator, mac, entry), ActuatorEvent(coordinator, mac, entry)]
    )


class _UrmetEvent(UrmetEntity, EventEntity):
    """Common wiring: subscribe to the gateway event stream on add."""

    def __init__(self, coordinator: UrmetCoordinator, mac: str, entry: UrmetConfigEntry) -> None:
        super().__init__(coordinator, mac)
        self._entry = entry

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.client.add_event_listener(self._handle_gateway_event))

    @callback
    def _handle_gateway_event(self, event: GatewayEvent) -> None:
        """React to one gateway event. Overridden per entity."""


class DoorbellEvent(_UrmetEvent):
    """``event.portier_sonnette``: the doorbell was pressed (DESIGN 6.4)."""

    _attr_translation_key = "sonnette"
    _attr_device_class = EventDeviceClass.DOORBELL

    def __init__(self, coordinator: UrmetCoordinator, mac: str, entry: UrmetConfigEntry) -> None:
        super().__init__(coordinator, mac, entry)
        self._attr_unique_id = f"{mac}_{KEY_DOORBELL}"
        self._attr_event_types = [EVENT_RING]
        self._last_fire: float | None = None

    @callback
    def _handle_gateway_event(self, event: GatewayEvent) -> None:
        if not isinstance(event, RingEvent):
            return
        window = float(self._entry.options.get(CONF_RING_COALESCE, DEFAULT_RING_COALESCE))
        now = time.monotonic()
        if self._last_fire is not None and now - self._last_fire < window:
            return
        self._last_fire = now
        doorphone = event.doorphone
        self._trigger_event(
            EVENT_RING,
            {
                "call_id": event.call_id,
                "doorphone": doorphone.mac if doorphone else None,
                "name": doorphone.name if doorphone else None,
            },
        )
        self.async_write_ha_state()


class ActuatorEvent(_UrmetEvent):
    """``event.portier_ouverture``: a door or gate open (DESIGN 6.4)."""

    _attr_translation_key = "ouverture"

    def __init__(self, coordinator: UrmetCoordinator, mac: str, entry: UrmetConfigEntry) -> None:
        super().__init__(coordinator, mac, entry)
        self._attr_unique_id = f"{mac}_{KEY_ACTUATOR}"
        self._attr_event_types = [ACTUATOR_DOOR, ACTUATOR_GATE]

    @callback
    def _handle_gateway_event(self, event: GatewayEvent) -> None:
        if not isinstance(event, OpenEvent):
            return
        if event.actuator not in self._attr_event_types:
            return
        pending = take_open(self.hass, self._entry.entry_id)
        # Attribute the open to the user who asked, so the logbook reads "opened
        # by <person>" rather than crediting the integration's own callback.
        if pending.context is not None:
            self.async_set_context(pending.context)
        self._trigger_event(
            event.actuator,
            {
                "acknowledged": event.acknowledged,
                "call_id": event.call_id,
                "origin": pending.origin,
            },
        )
        self.async_write_ha_state()
