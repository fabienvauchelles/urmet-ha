"""The ``urmet.*`` actions: parse the call, pick the entry, format the reply.

Registered once per Home Assistant instance from ``async_setup``, like the card's
WebSocket API, so the action surface does not come and go with a config entry.
The commands themselves live in ``commands.py``; nothing here names a gateway path.

Every action resolves which doorphone it is aimed at from the call's own target:
a ``device_id`` or an explicit ``entry_id``. With one panel set up the target may
be left out, which is what every existing automation and the card do. With more
than one and no target named, the action refuses rather than picking a panel: an
open fired at the wrong door is worse than an open that did not happen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.const import ATTR_DEVICE_ID, ENTITY_MATCH_NONE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .commands import (
    ATTR_ACKNOWLEDGED,
    ATTR_ACTUATOR,
    ATTR_CALL_ID,
    ATTR_MUTED,
    ATTR_WANT_VIDEO,
    async_answer,
    async_hang_up,
    async_look,
    async_open,
    async_set_microphone,
)
from .const import ACTUATOR_DOOR, ACTUATOR_GATE, DOMAIN, ORIGIN_SERVICE
from .coordinator import UrmetConfigEntry

ACTUATORS = (ACTUATOR_DOOR, ACTUATOR_GATE)

SERVICE_ANSWER = "answer"
SERVICE_HANG_UP = "hang_up"
SERVICE_LOOK = "look"
SERVICE_OPEN = "open"
SERVICE_SET_MICROPHONE = "set_microphone"

ATTR_ENTRY_ID = "entry_id"


# --- Target resolution -----------------------------------------------------


def _resolve_entry(call: ServiceCall) -> UrmetConfigEntry:
    """The loaded doorphone this call is aimed at (DESIGN 6.5).

    Raises when nothing is set up, when the named target is not a loaded Urmet
    entry, or when several panels are set up and the call named none of them.
    """
    entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("no Urmet doorphone is set up")
    entry_id = _targeted_entry_id(call)
    if entry_id is None:
        return _sole_entry(entries)
    for entry in entries:
        if entry.entry_id == entry_id:
            return entry
    raise ServiceValidationError(f"no loaded Urmet doorphone for target {entry_id!r}")


def _sole_entry(entries: list[UrmetConfigEntry]) -> UrmetConfigEntry:
    if len(entries) > 1:
        raise ServiceValidationError(
            "several Urmet doorphones are set up: name one with device_id or entry_id"
        )
    return entries[0]


def _targeted_entry_id(call: ServiceCall) -> str | None:
    """The entry id the call names, directly or through a device. ``None`` if it names none."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    if isinstance(entry_id, str):
        return entry_id
    device_id = _sole_device_id(call.data.get(ATTR_DEVICE_ID))
    if device_id is None:
        return None
    device = dr.async_get(call.hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(f"unknown device {device_id!r}")
    owned = [entry_id for entry_id in device.config_entries if _is_urmet(call.hass, entry_id)]
    if len(owned) != 1:
        raise ServiceValidationError(f"device {device_id!r} is not one Urmet doorphone")
    return owned[0]


def _sole_device_id(raw: object) -> str | None:
    """The single device a target names. A list of several is refused, not sampled."""
    if raw == ENTITY_MATCH_NONE:
        return None
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, list) or not raw:
        return None
    if len(raw) > 1:
        raise ServiceValidationError("name one doorphone: this call targets several devices")
    return str(raw[0])


def _is_urmet(hass: HomeAssistant, entry_id: str) -> bool:
    entry = hass.config_entries.async_get_entry(entry_id)
    return entry is not None and entry.domain == DOMAIN


# --- Service handlers ------------------------------------------------------


async def _handle_open(call: ServiceCall) -> ServiceResponse:
    acknowledged = await async_open(
        _resolve_entry(call),
        actuator=call.data[ATTR_ACTUATOR],
        origin=ORIGIN_SERVICE,
        context=call.context,
    )
    return {ATTR_ACKNOWLEDGED: acknowledged}


async def _handle_answer(call: ServiceCall) -> None:
    await async_answer(_resolve_entry(call), call_id=call.data.get(ATTR_CALL_ID))


async def _handle_hang_up(call: ServiceCall) -> None:
    await async_hang_up(_resolve_entry(call), call_id=call.data.get(ATTR_CALL_ID))


async def _handle_look(call: ServiceCall) -> ServiceResponse:
    return await async_look(_resolve_entry(call), want_video=call.data[ATTR_WANT_VIDEO])


async def _handle_set_microphone(call: ServiceCall) -> None:
    await async_set_microphone(_resolve_entry(call), muted=call.data[ATTR_MUTED])


# --- Schemas and registration ----------------------------------------------

# Every action accepts the same optional target: Home Assistant's own device
# picker, or the entry id the card already speaks. One dict, so no action can
# grow a target the others do not have.
# voluptuous keys are marker instances of several classes, and a dict is
# invariant in its key type, so the merged literals are typed loosely on purpose.
_SchemaDict = dict[Any, Any]

_TARGET_FIELDS: _SchemaDict = {
    **cv.TARGET_SERVICE_FIELDS,
    vol.Optional(ATTR_ENTRY_ID): selector.TextSelector(),
}
_CALL_ID_FIELD: _SchemaDict = {vol.Optional(ATTR_CALL_ID): selector.TextSelector()}

_ANSWER_SCHEMA = vol.Schema({**_TARGET_FIELDS, **_CALL_ID_FIELD})
_HANG_UP_SCHEMA = vol.Schema({**_TARGET_FIELDS, **_CALL_ID_FIELD})
_LOOK_SCHEMA = vol.Schema(
    {**_TARGET_FIELDS, vol.Optional(ATTR_WANT_VIDEO, default=True): selector.BooleanSelector()}
)
_OPEN_SCHEMA = vol.Schema({**_TARGET_FIELDS, vol.Required(ATTR_ACTUATOR): vol.In(ACTUATORS)})
_SET_MICROPHONE_SCHEMA = vol.Schema({**_TARGET_FIELDS, vol.Required(ATTR_MUTED): cv.boolean})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the ``urmet.*`` actions once per Home Assistant instance."""
    hass.services.async_register(DOMAIN, SERVICE_ANSWER, _handle_answer, schema=_ANSWER_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_HANG_UP, _handle_hang_up, schema=_HANG_UP_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOOK,
        _handle_look,
        schema=_LOOK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN,
        _handle_open,
        schema=_OPEN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MICROPHONE,
        _handle_set_microphone,
        schema=_SET_MICROPHONE_SCHEMA,
    )
