"""Binary sensors: SIP registration and a live call (DESIGN 6.3).

Both read the coordinator snapshot, so they never disagree with the state the
gateway last pushed. ``binary_sensor.portier_sip`` is a diagnostic connectivity
sensor on the panel's SIP binding; ``binary_sensor.portier_appel_en_cours`` is on
whenever a dialog is ringing, connecting or streaming.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import KEY_CALL_ACTIVE, KEY_REGISTERED
from .coordinator import UrmetConfigEntry, UrmetCoordinator
from .entity import UrmetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrmetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the registration and call-active binary sensors."""
    coordinator = entry.runtime_data.coordinator
    mac = str(entry.unique_id)
    async_add_entities(
        [RegistrationBinarySensor(coordinator, mac), CallActiveBinarySensor(coordinator, mac)]
    )


class RegistrationBinarySensor(UrmetEntity, BinarySensorEntity):
    """``binary_sensor.portier_sip``: the SIP binding is registered."""

    _attr_translation_key = "sip"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{KEY_REGISTERED}"

    @property
    def is_on(self) -> bool | None:
        data = self.state_view
        return None if data is None else data.registered


class CallActiveBinarySensor(UrmetEntity, BinarySensorEntity):
    """``binary_sensor.portier_appel_en_cours``: a dialog is live."""

    _attr_translation_key = "appel_en_cours"

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{KEY_CALL_ACTIVE}"

    @property
    def is_on(self) -> bool | None:
        data = self.state_view
        if data is None:
            return None
        return any(call.state.is_active for call in data.calls)
