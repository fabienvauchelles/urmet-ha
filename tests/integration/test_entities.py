"""Every entity's unique_id, device_class and entity_category (DESIGN 6.3).

The table below is the DESIGN 6.3 entity table, transcribed. The test asserts the
integration creates exactly these entities, each with the right unique_id suffix,
device_class and entity_category, so a later refactor cannot silently drop a
diagnostic category (which would change recorder/exposure behaviour) or a
device_class (which drives the automation UI).
"""

from __future__ import annotations

from gateway_double import DOORPHONE_MAC, FakeGateway
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.urmet.const import CONF_HOST, CONF_PORT, DOMAIN

# suffix -> (device_class, entity_category), both as their string value or None.
EXPECTED: dict[str, tuple[str | None, str | None]] = {
    "doorbell": ("doorbell", None),
    "actuator": (None, None),
    "open_door": (None, None),
    "open_gate": (None, None),
    "look": (None, None),
    "answer": (None, None),
    "hangup": (None, None),
    "mic": (None, "config"),
    "registered": ("connectivity", "diagnostic"),
    "call_active": (None, None),
    "call_state": ("enum", None),
    "last_ring": ("timestamp", None),
    "ring_total": (None, "diagnostic"),
    "door_total": (None, "diagnostic"),
    "gate_total": (None, "diagnostic"),
    "reg_status": (None, "diagnostic"),
    "last_error": (None, "diagnostic"),
}


async def _setup(hass: HomeAssistant, gateway: FakeGateway) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: gateway.host, CONF_PORT: gateway.port},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entity_table(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = await _setup(hass, fake_gateway)
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    by_unique = {e.unique_id: e for e in entries}

    # Exactly the DESIGN 6.3 set, no more and no less.
    assert set(by_unique) == {f"{DOORPHONE_MAC}_{s}" for s in EXPECTED}

    for suffix, (device_class, category) in EXPECTED.items():
        reg = by_unique[f"{DOORPHONE_MAC}_{suffix}"]
        assert reg.original_device_class == device_class, suffix
        got_category = reg.entity_category.value if reg.entity_category else None
        assert got_category == category, suffix

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_event_types_and_enum_options(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = await _setup(hass, fake_gateway)
    registry = er.async_get(hass)
    by_unique = {
        e.unique_id: e for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    doorbell = by_unique[f"{DOORPHONE_MAC}_doorbell"]
    assert doorbell.capabilities["event_types"] == ["ring"]
    actuator = by_unique[f"{DOORPHONE_MAC}_actuator"]
    assert actuator.capabilities["event_types"] == ["door", "gate"]

    call_state = by_unique[f"{DOORPHONE_MAC}_call_state"]
    assert call_state.capabilities["options"] == [
        "idle",
        "ringing",
        "connecting",
        "streaming",
        "ended",
        "error",
    ]

    diagnostic = {s for s, (_dc, cat) in EXPECTED.items() if cat == "diagnostic"}
    for suffix in diagnostic:
        reg = by_unique[f"{DOORPHONE_MAC}_{suffix}"]
        assert reg.entity_category is EntityCategory.DIAGNOSTIC

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
