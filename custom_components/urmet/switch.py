"""The microphone switch (DESIGN 6.3).

``switch.portier_micro`` reflects the browser-to-panel microphone: on means the
household can be heard at the panel, off means muted. The service starts muted
(DESIGN 5.2), and the gateway pushes a fresh ``state`` after every change, so the
switch reads its own truth from the coordinator rather than guessing optimistically.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .commands import async_set_microphone
from .const import KEY_MIC
from .coordinator import UrmetConfigEntry, UrmetCoordinator
from .entity import UrmetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrmetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the microphone switch."""
    coordinator = entry.runtime_data.coordinator
    mac = str(entry.unique_id)
    async_add_entities([MicrophoneSwitch(coordinator, mac, entry)])


class MicrophoneSwitch(UrmetEntity, SwitchEntity):
    """On when the microphone is open towards the panel (DESIGN 6.3)."""

    _attr_translation_key = "micro"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: UrmetCoordinator, mac: str, entry: UrmetConfigEntry) -> None:
        super().__init__(coordinator, mac)
        self._entry = entry
        self._attr_unique_id = f"{mac}_{KEY_MIC}"

    @property
    def is_on(self) -> bool | None:
        data = self.state_view
        return None if data is None else not data.mic_muted

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_set_microphone(self._entry, muted=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_set_microphone(self._entry, muted=True)
