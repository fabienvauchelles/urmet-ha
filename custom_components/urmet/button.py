"""Button entities: the two openers and the call controls (DESIGN 6.3).

The gate is a button, not a ``cover``, because the motor is step-by-step with no
position and no state query, and a ``cover`` would publish states that cannot be
known (DESIGN 6.3). Each button calls the shared command layer underneath, so a
press takes the exact same path to the gateway as the matching ``urmet.*``
action (DESIGN 6.5). The openers pass origin ``card``: a press is a UI gesture.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTUATOR_DOOR,
    ACTUATOR_GATE,
    KEY_ANSWER,
    KEY_HANGUP,
    KEY_LOOK,
    KEY_OPEN_DOOR,
    KEY_OPEN_GATE,
    ORIGIN_CARD,
)
from .coordinator import UrmetConfigEntry, UrmetCoordinator
from .entity import UrmetEntity
from .services import (
    async_answer,
    async_hang_up,
    async_look,
    async_open,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrmetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the five doorphone buttons."""
    coordinator = entry.runtime_data.coordinator
    mac = str(entry.unique_id)
    async_add_entities(
        [
            OpenDoorButton(coordinator, mac, entry),
            OpenGateButton(coordinator, mac, entry),
            LookButton(coordinator, mac, entry),
            AnswerButton(coordinator, mac, entry),
            HangUpButton(coordinator, mac, entry),
        ]
    )


class _UrmetButton(UrmetEntity, ButtonEntity):
    """A button bound to the one entry, carrying it for the command layer."""

    _key: str
    _translation_key: str

    def __init__(self, coordinator: UrmetCoordinator, mac: str, entry: UrmetConfigEntry) -> None:
        super().__init__(coordinator, mac)
        self._entry = entry
        self._attr_unique_id = f"{mac}_{self._key}"
        self._attr_translation_key = self._translation_key


class OpenDoorButton(_UrmetButton):
    _key = KEY_OPEN_DOOR
    _translation_key = "porte"

    async def async_press(self) -> None:
        await async_open(
            self.hass,
            self._entry,
            actuator=ACTUATOR_DOOR,
            origin=ORIGIN_CARD,
            context=self._context,
        )


class OpenGateButton(_UrmetButton):
    _key = KEY_OPEN_GATE
    _translation_key = "portail"

    async def async_press(self) -> None:
        await async_open(
            self.hass,
            self._entry,
            actuator=ACTUATOR_GATE,
            origin=ORIGIN_CARD,
            context=self._context,
        )


class LookButton(_UrmetButton):
    _key = KEY_LOOK
    _translation_key = "regarder"

    async def async_press(self) -> None:
        await async_look(self.hass, self._entry, want_video=True)


class AnswerButton(_UrmetButton):
    _key = KEY_ANSWER
    _translation_key = "repondre"

    async def async_press(self) -> None:
        await async_answer(self.hass, self._entry, call_id=None)


class HangUpButton(_UrmetButton):
    _key = KEY_HANGUP
    _translation_key = "raccrocher"

    async def async_press(self) -> None:
        await async_hang_up(self.hass, self._entry, call_id=None)
