"""Base entity for every Urmet platform (DESIGN 6.3).

All entities are coordinator entities on the one device. ``has_entity_name`` is
set so ids come out as ``portier_<slug>``; the device carries the panel MAC as
its only identifier, so a reconfigure that keeps the same panel keeps the same
device and history.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER, MODEL, SUGGESTED_AREA
from .coordinator import UrmetCoordinator
from .models import StateView


class UrmetEntity(CoordinatorEntity[UrmetCoordinator]):
    """Common device info and availability for the Urmet entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UrmetCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            suggested_area=SUGGESTED_AREA,
        )

    @property
    def state_view(self) -> StateView | None:
        """The latest gateway snapshot, or ``None`` before the first update."""
        return self.coordinator.data

    @property
    def available(self) -> bool:
        """Available while the gateway is reachable and a snapshot exists."""
        return super().available and self.coordinator.data is not None
