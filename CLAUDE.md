# urmet-ha

Home Assistant add-on, integration and Lovelace card for an Urmet 2Voice video
doorphone, built on the `urmet-sdk` submodule. The implementation contract is the
DESIGN document referenced by each work package; this file is the standing briefing.

## Deliverables

- `addon/urmet-gateway/` : HA OS add-on. The gateway terminates the Urmet SIP leg
  through `urmet-sdk` and originates a WebRTC leg. HTTP/WebSocket on port 8099.
- `custom_components/urmet/` : the integration (domain `urmet`, `local_push`).
- `card/` : `custom:urmet-portier-card`, Lit + TypeScript, built by CI.

## Standards (non-negotiable)

- Python 3.12. Clean Architecture, dependency rule enforced, SOLID.
- Every source file strictly under 300 lines. Each module has a line budget in the
  DESIGN. Over budget means split along a domain boundary, never compress.
- ruff line-length 100, mypy strict, typed errors never swallowed.
- Full-scenario tests only, driven through the public surface, against the SDK
  doubles (`urmet_sdk.testing`). No network, no `pjsua2`, no `ffmpeg` (one exception).
  Deterministic and independent.
- English on disk. No emdash (U+2014) anywhere. No AI-flavored phrasing.
- Delete nothing you did not create. Do not touch files outside your work package.

## Layers and the import ban

Dependency rule, strictly inward:

```
main  ->  http  ->  usecases  ->  domain
          sip    ->  usecases
          media  ->  usecases
```

- `domain` imports nothing from the project and no framework.
- `usecases` imports `domain` only; never `aiohttp`, `aiortc`, `av`, `pjsua2`.
- `sip` and `media` may import `domain` and `usecases`. `media` owns `aiortc` and
  `av`; `sip` reaches the native stack only through the injected SDK object.
- `http` may import `domain`, `usecases` and `aiohttp`.
- `main` is the composition root and the only module that names `PjsipTransport`,
  `CloudClient`, `UrmetClient` and `aiortc`.

Enforced by ruff `flake8-tidy-imports` (TID251): the root `pyproject.toml` bans
nothing globally, and one nested `ruff.toml` per layer (extending the root) carries
that layer's ban list. Add code that violates the rule and `make gateway` fails at
its ruff step, naming the exact import.

## Gateway module map (`addon/urmet-gateway/urmet_gateway/`)

- `main.py` composition root; `settings.py` `GatewaySettings`; `constants.py` the
  measured constants.
- `domain/` : `models.py`, `errors.py`, `ports.py` (the Protocols the use cases need).
- `usecases/` : `service.py`, `calls.py`, `sessions.py`, `events.py`, `state.py`,
  `supervision.py`.
- `sip/` : `worker.py` (one SDK thread), `bridge.py` (callbacks to the loop),
  `tap.py`.
- `media/` : `session.py`, `pipeline.py`, `encoder.py`, `track.py`, `picture_wait.py`,
  `watchdog.py`, and `audio/` (`bridge.py`, `tracks.py`, `g711.py`, `measure.py`).
- `http/` : `app.py`, `rest.py`, `ws.py`, `errors.py`, `models.py`; `diag/` the
  ingress diagnostics page.

Two thread crossings and nothing else owns either: into the SDK through the single
`SdkWorker` thread; out of the SDK through `loop.call_soon_threadsafe`. The media
clock thread is a third, stricter thread: copy, count, return.

## Commands

Three areas, each with its own interpreter and config: gateway (`.venv`, root
`pyproject.toml`), integration (`.venv-ha`, `qa/integration-*`), card (`card/`).

```
make build       # provision all three areas (both venvs + card npm deps)
make check       # unified gate: gateway + integration + card
make gateway     # ruff + mypy + pytest over the add-on          (.venv)
make integration # ruff + mypy + pytest over custom_components    (.venv-ha)
make card        # tsc --noEmit + vitest + rollup bundle          (card/)
```

`tests/isolation.py` raises through `BaseException` on `import pjsua2` or a
non-loopback socket, so a violation fails the run rather than becoming a caught 500.

## Verification before closing a task

Run `make check`; it must exit 0 with zero warnings. Confirm every modified file is
under 300 lines and its DESIGN budget. Remove unused exports and orphans. Update
`README.md` and this file when the module map or the commands change.
