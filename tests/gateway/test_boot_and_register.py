"""Boot, then register: the port opens before the SDK is up, muted.

Registration crosses the cloud and the registrar and takes as long as they take,
so a gateway that answered nothing until then would be one a supervisor calls
dead. ``/api/health`` answers while the binding does not exist yet, ``/api/state``
says so honestly, and the stream reports the binding the moment the registrar
grants it. Booting also closes the microphone, asserted on the transport rather
than on what the service says: the composition root forces the null sound device
on, and this stage carries no audio, so nothing should be transmitted at all.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from urmet_sdk import Settings

from urmet_gateway.main import _variables, force_null_sound_device

from .http_support import DOORPHONE_MAC, http_harness


async def test_health_answers_before_the_binding_that_state_then_reports() -> None:
    async with http_harness(gate_start=True) as h:
        # The boot task is held at REGISTER, yet the port already answers.
        health = await h.get("/api/health")
        assert health.status == 200
        assert await health.json() == {"ok": True}

        cold = await (await h.get("/api/state")).json()
        assert cold["registered"] is False
        assert cold["doorphone"] == {"mac": DOORPHONE_MAC, "name": "Front Gate"}
        assert cold["calls"] == []
        assert cold["sessions"] == []

        async with h.events() as stream:
            assert (await stream.expect("state"))["registered"] is False
            h.release_start()
            registration = await stream.until("registration", registered=True)
            assert registration["status_code"] == 200
            assert (await stream.until("state"))["registered"] is True

        # Asked of the transport: the point is the stack was told, and that a boot
        # carrying no audio placed no call and answered none.
        assert h.transport.mic_muted() is True
        assert len(h.transport.registrations) == 1
        assert h.transport.answered == []
        assert h.transport.invites == []


def test_null_sound_device_is_forced() -> None:
    settings = Settings(_env_file=None, email="tester@example.com", password="secret")
    assert settings.null_sound_device is False
    assert force_null_sound_device(settings).null_sound_device is True


def test_missing_config_names_the_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("URMET_EMAIL", raising=False)
    monkeypatch.delenv("URMET_PASSWORD", raising=False)
    try:
        Settings(_env_file=None)
    except ValidationError as error:
        message = _variables(error)
    else:
        raise AssertionError("expected a ValidationError for the missing credentials")
    assert "URMET_EMAIL" in message
    assert "URMET_PASSWORD" in message
