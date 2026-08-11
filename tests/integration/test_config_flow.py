"""Config, reconfigure and options flow scenarios (DESIGN 6.1)."""

from __future__ import annotations

from gateway_double import DOORPHONE_MAC, OTHER_MAC, FakeGateway
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.urmet.const import CONF_HOST, CONF_PORT, DOMAIN


async def test_user_flow_success(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Portier"
    assert result["data"] == {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port}
    entry = result["result"]
    assert entry.unique_id == DOORPHONE_MAC

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_user_flow_no_doorphone(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    fake_gateway.has_doorphone = False
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )

    # A gateway that has not seen the panel yet is a retryable state, not a
    # dead-end: the form comes back with an actionable error, never an abort.
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_doorphone"}


def _discovery(fake_gateway: FakeGateway) -> HassioServiceInfo:
    return HassioServiceInfo(
        config={CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
        name="Urmet doorphone gateway",
        slug="urmet_gateway",
        uuid="0123456789abcdef",
    )


async def test_hassio_discovery_flow(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=_discovery(fake_gateway)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == DOORPHONE_MAC
    assert entry.data == {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_hassio_discovery_already_configured(
    hass: HomeAssistant, fake_gateway: FakeGateway
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=_discovery(fake_gateway)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_cannot_connect(hass: HomeAssistant, dead_port: int) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: dead_port}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_success(hass: HomeAssistant, fake_gateway: FakeGateway) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOORPHONE_MAC,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 1},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant, fake_gateway: FakeGateway
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=OTHER_MAC,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 1},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: fake_gateway.host, CONF_PORT: fake_gateway.port},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
