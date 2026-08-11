"""Sensors: call state, last ring, counters and diagnostics (DESIGN 6.3).

``sensor.portier_etat_appel`` reads the coordinator snapshot. The counters and
the last-ring timestamp survive a restart through ``RestoreSensor`` and advance
on the gateway event stream, so their long-term statistics are unbroken; none is
named ``*_person_count`` or ``*_all_count``, which ``recorder.exclude`` would
silently swallow (recon 05 section 7). ``code_sip`` and ``derniere_erreur`` are
transient diagnostics fed by the registration and WebRTC events and are not
restored, so a stale code never outlives a restart.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ACTUATOR_DOOR,
    ACTUATOR_GATE,
    KEY_CALL_STATE,
    KEY_DOOR_TOTAL,
    KEY_GATE_TOTAL,
    KEY_LAST_ERROR,
    KEY_LAST_RING,
    KEY_REG_STATUS,
    KEY_RING_TOTAL,
)
from .coordinator import UrmetConfigEntry, UrmetCoordinator
from .entity import UrmetEntity
from .events import (
    GatewayEvent,
    OpenEvent,
    RegistrationEvent,
    RingEvent,
    WebrtcEvent,
)
from .models import CallState

# What the ENUM sensor advertises: every call state the gateway names. UNKNOWN
# is deliberately not one of them, so a state this build does not know reports
# None rather than a value outside the declared options.
CALL_STATE_OPTIONS = [state.value for state in CallState if state is not CallState.UNKNOWN]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrmetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the call-state sensor, the counters and the diagnostics."""
    coordinator = entry.runtime_data.coordinator
    mac = str(entry.unique_id)
    async_add_entities(
        [
            CallStateSensor(coordinator, mac),
            LastRingSensor(coordinator, mac),
            CounterSensor(coordinator, mac, KEY_RING_TOTAL, "sonneries", _is_ring),
            CounterSensor(coordinator, mac, KEY_DOOR_TOTAL, "ouvertures_porte", _is_door),
            CounterSensor(coordinator, mac, KEY_GATE_TOTAL, "ouvertures_portail", _is_gate),
            RegStatusSensor(coordinator, mac),
            LastErrorSensor(coordinator, mac),
        ]
    )


class CallStateSensor(UrmetEntity, SensorEntity):
    """``sensor.portier_etat_appel``: the current dialog's state (enum)."""

    _attr_translation_key = "etat_appel"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CALL_STATE_OPTIONS

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{KEY_CALL_STATE}"

    @property
    def native_value(self) -> str | None:
        data = self.state_view
        if data is None:
            return None
        active = next((c.state for c in data.calls if c.state.is_active), None)
        value = active or (data.calls[-1].state if data.calls else CallState.IDLE)
        return value.value if value in CALL_STATE_OPTIONS else None


class _EventSensor(UrmetEntity, RestoreSensor):
    """A sensor advanced by the gateway event stream, restored on restart."""

    _restore_enabled = True

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._value: Any = self._default()

    def _default(self) -> Any:
        return None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._restore_enabled:
            last = await self.async_get_last_sensor_data()
            if last is not None and last.native_value is not None:
                self._value = last.native_value
        self.async_on_remove(self.coordinator.client.add_event_listener(self._handle))

    @callback
    def _handle(self, event: GatewayEvent) -> None:
        new = self._reduce(event)
        if new is not None and new != self._value:
            self._value = new
            self.async_write_ha_state()

    def _reduce(self, event: GatewayEvent) -> Any:
        raise NotImplementedError

    @property
    def native_value(self) -> Any:
        return self._value


class LastRingSensor(_EventSensor):
    """``sensor.portier_derniere_sonnerie``: when the bell last rang."""

    _attr_translation_key = "derniere_sonnerie"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{KEY_LAST_RING}"

    def _reduce(self, event: GatewayEvent) -> datetime | None:
        if isinstance(event, RingEvent):
            return event.at or dt_util.utcnow()
        return None


class CounterSensor(_EventSensor):
    """A ``total_increasing`` count advanced by a matching event (DESIGN 6.3)."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UrmetCoordinator,
        mac: str,
        key: str,
        translation_key: str,
        matches: Callable[[GatewayEvent], bool],
    ) -> None:
        self._attr_translation_key = translation_key
        self._matches = matches
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{key}"

    def _default(self) -> int:
        return 0

    def _reduce(self, event: GatewayEvent) -> int | None:
        return int(self._value) + 1 if self._matches(event) else None


class RegStatusSensor(_EventSensor):
    """``sensor.portier_code_sip``: the last SIP status code (diagnostic)."""

    _attr_translation_key = "code_sip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _restore_enabled = False

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{KEY_REG_STATUS}"

    def _reduce(self, event: GatewayEvent) -> int | None:
        return event.status_code if isinstance(event, RegistrationEvent) else None


class LastErrorSensor(_EventSensor):
    """``sensor.portier_derniere_erreur``: the last reported reason (diagnostic)."""

    _attr_translation_key = "derniere_erreur"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _restore_enabled = False

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{KEY_LAST_ERROR}"

    def _reduce(self, event: GatewayEvent) -> str | None:
        if isinstance(event, RegistrationEvent) and event.reason:
            return event.reason
        if isinstance(event, WebrtcEvent) and event.reason and event.state.is_faulted:
            return event.reason
        return None


def _is_ring(event: GatewayEvent) -> bool:
    return isinstance(event, RingEvent)


def _is_door(event: GatewayEvent) -> bool:
    return isinstance(event, OpenEvent) and event.actuator == ACTUATOR_DOOR and event.acknowledged


def _is_gate(event: GatewayEvent) -> bool:
    return isinstance(event, OpenEvent) and event.actuator == ACTUATOR_GATE and event.acknowledged
