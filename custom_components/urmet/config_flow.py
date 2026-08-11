"""Config, reconfigure and options flows (DESIGN 6.1).

The user step collects the add-on host and port, then probes the gateway: a
``GET /api/health`` followed by a ``GET /api/state`` whose ``doorphone.mac``
becomes the unique id. There is no reauth step: the cloud credentials live in the
add-on options, so an authentication failure surfaces as a Repairs issue naming
the add-on (WP9), never as a HA reauth flow.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import GatewayClient, GatewayConnectionError
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RING_COALESCE,
    CONF_SHOW_TECH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_RING_COALESCE,
    DEFAULT_SHOW_TECH,
    DEVICE_NAME,
    DOMAIN,
)
from .coordinator import UrmetConfigEntry


class UrmetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect the add-on host and port; key the entry on the panel MAC."""

    VERSION = 1

    _title: str = DEVICE_NAME

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = await self._probe(user_input)
            except GatewayConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if mac is None:
                    return self.async_abort(reason="no_doorphone")
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=self._title, data=self._data(user_input))
        return self.async_show_form(
            step_id="user", data_schema=self._schema(user_input), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = await self._probe(user_input)
            except GatewayConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if mac is None:
                    errors["base"] = "no_doorphone"
                else:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry, data_updates=self._data(user_input)
                    )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(user_input or entry.data),
            errors=errors,
        )

    async def _probe(self, user_input: Mapping[str, Any]) -> str | None:
        """Return the panel MAC, ``None`` if the gateway knows no panel yet."""
        client = GatewayClient(self.hass, user_input[CONF_HOST], user_input[CONF_PORT])
        await client.async_check_health()
        state = await client.async_get_state()
        if state.doorphone is None:
            return None
        self._title = state.doorphone.name or DEVICE_NAME
        return state.doorphone.mac

    @staticmethod
    def _data(user_input: Mapping[str, Any]) -> dict[str, Any]:
        return {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}

    @staticmethod
    def _schema(values: Mapping[str, Any] | None) -> vol.Schema:
        values = values or {}
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=values.get(CONF_HOST, DEFAULT_HOST)): str,
                vol.Required(CONF_PORT, default=values.get(CONF_PORT, DEFAULT_PORT)): cv.port,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: UrmetConfigEntry) -> UrmetOptionsFlow:
        return UrmetOptionsFlow()


class UrmetOptionsFlow(OptionsFlow):
    """Runtime options: ring coalescing window and the tech panel toggle."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RING_COALESCE,
                    default=options.get(CONF_RING_COALESCE, DEFAULT_RING_COALESCE),
                ): vol.All(int, vol.Range(min=0, max=60)),
                vol.Optional(
                    CONF_SHOW_TECH,
                    default=options.get(CONF_SHOW_TECH, DEFAULT_SHOW_TECH),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
