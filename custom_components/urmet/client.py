"""HTTP + WebSocket transport to the ``urmet-gateway`` add-on (DESIGN 5.2, 5.3).

``GatewayClient`` owns the single aiohttp session against the add-on: the HTTP
helpers the config flow and the entity platforms call, and the long-lived
``GET /api/events`` WebSocket. It reconnects with exponential backoff and logs
once per backoff step, never once per attempt (Silver: no log spam). Every
decoded frame is fanned out to registered listeners as a typed event.

This is the outer-layer transport adapter, kept apart from the coordinator glue
in ``coordinator.py`` so the push coordinator depends on the client and never the
other way round.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Callable
from dataclasses import dataclass
from json import loads as _json_loads
from typing import Any

import aiohttp
from aiohttp import ClientTimeout, WSMsgType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BACKOFF_JITTER,
    BACKOFF_SCHEDULE_S,
    DOMAIN,
    EVENTS_PATH,
    HEALTH_PATH,
    LOGGER,
    REQUEST_TIMEOUT_S,
    STATE_PATH,
    WS_HEARTBEAT_S,
)
from .events import GatewayEvent, parse_event
from .models import StateView


class GatewayConnectionError(HomeAssistantError):
    """The gateway could not be reached or answered off-contract."""


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    """A raw gateway reply for the command routes (DESIGN 5.2). WP8 maps status."""

    status: int
    body: dict[str, Any]


class GatewayClient:
    """HTTP + WebSocket client for one ``urmet-gateway`` add-on."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self._hass = hass
        self._host = host
        self._port = int(port)
        self._session = async_get_clientsession(hass)
        self._event_listeners: set[Callable[[GatewayEvent], None]] = set()
        self._conn_listeners: set[Callable[[bool], None]] = set()
        self._task: asyncio.Task[None] | None = None
        self._closing = False
        self._connected = False
        self._degraded = False

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def connected(self) -> bool:
        return self._connected

    # --- HTTP -------------------------------------------------------------

    async def async_check_health(self) -> None:
        """Raise ``GatewayConnectionError`` unless GET /api/health is ok."""
        body = await self._get_json(HEALTH_PATH)
        if body.get("ok") is not True:
            raise GatewayConnectionError("gateway health check did not return ok")

    async def async_get_state(self) -> StateView:
        return StateView.from_dict(await self._get_json(STATE_PATH))

    async def async_request(
        self, method: str, path: str, *, json: Any | None = None
    ) -> GatewayResponse:
        """Call a command route, returning its status and decoded body."""
        try:
            async with self._session.request(
                method,
                self.base_url + path,
                json=json,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT_S),
            ) as resp:
                raw = await resp.read()
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GatewayConnectionError(f"gateway request {method} {path} failed: {err}") from err
        body: dict[str, Any] = {}
        if raw:
            with contextlib.suppress(ValueError):
                decoded = _json_loads(raw)
                if isinstance(decoded, dict):
                    body = decoded
        return GatewayResponse(status=status, body=body)

    async def _get_json(self, path: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                self.base_url + path, timeout=ClientTimeout(total=REQUEST_TIMEOUT_S)
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GatewayConnectionError(
                f"cannot reach the gateway at {self.base_url}{path}: {err}"
            ) from err
        if not isinstance(body, dict):
            raise GatewayConnectionError("gateway returned a non-object body")
        return body

    # --- Listeners --------------------------------------------------------

    def add_event_listener(self, callback_: Callable[[GatewayEvent], None]) -> Callable[[], None]:
        self._event_listeners.add(callback_)
        return lambda: self._event_listeners.discard(callback_)

    def add_connection_listener(self, callback_: Callable[[bool], None]) -> Callable[[], None]:
        self._conn_listeners.add(callback_)
        return lambda: self._conn_listeners.discard(callback_)

    # --- Lifecycle --------------------------------------------------------

    async def async_start(self) -> None:
        if self._task is None:
            self._closing = False
            self._task = self._hass.async_create_background_task(
                self._run(), name=f"{DOMAIN}_events_{self._host}_{self._port}"
            )

    async def async_stop(self) -> None:
        self._closing = True
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._set_connected(False)

    # --- Internals --------------------------------------------------------

    async def _run(self) -> None:
        attempt = 0
        while not self._closing:
            connected = False
            try:
                connected = await self._consume()
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                LOGGER.debug("Urmet gateway event stream error: %s", err)
            except Exception:
                LOGGER.exception("Urmet gateway event stream crashed")
            if self._closing:
                break
            if connected:
                attempt = 0
            delay = self._delay_for(attempt)
            if attempt < len(BACKOFF_SCHEDULE_S):
                LOGGER.warning(
                    "Urmet gateway event stream unavailable, reconnecting in %.0fs",
                    delay,
                )
            attempt += 1
            self._degraded = True
            await asyncio.sleep(delay)

    async def _consume(self) -> bool:
        async with self._session.ws_connect(
            self.base_url + EVENTS_PATH, heartbeat=WS_HEARTBEAT_S
        ) as ws:
            if self._degraded:
                LOGGER.info("Urmet gateway event stream reconnected")
                self._degraded = False
            self._set_connected(True)
            try:
                async for msg in ws:
                    if msg.type is WSMsgType.TEXT:
                        self._dispatch_event(msg.data)
                    elif msg.type in (
                        WSMsgType.ERROR,
                        WSMsgType.CLOSED,
                        WSMsgType.CLOSING,
                    ):
                        break
            finally:
                self._set_connected(False)
            return True

    def _dispatch_event(self, raw: str) -> None:
        try:
            data = _json_loads(raw)
        except ValueError:
            LOGGER.debug("Urmet gateway sent a non-JSON frame, dropped")
            return
        if not isinstance(data, dict):
            return
        event = parse_event(data)
        for listener in list(self._event_listeners):
            try:
                listener(event)
            except Exception:
                LOGGER.exception("Urmet event listener raised")

    def _set_connected(self, value: bool) -> None:
        if value == self._connected:
            return
        self._connected = value
        for listener in list(self._conn_listeners):
            try:
                listener(value)
            except Exception:
                LOGGER.exception("Urmet connection listener raised")

    def _delay_for(self, attempt: int) -> float:
        base = BACKOFF_SCHEDULE_S[min(attempt, len(BACKOFF_SCHEDULE_S) - 1)]
        jitter = base * BACKOFF_JITTER
        return base + random.uniform(-jitter, jitter)
