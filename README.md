# urmet-ha

Home Assistant integration for an Urmet 2Voice video doorphone (Mini Note kit,
1722/958 module). Three deliverables live in this one repository and are installed
in this order:

1. **Add-on: Urmet doorphone gateway** (`addon/urmet-gateway/`). A Home Assistant
   OS add-on that terminates the Urmet SIP leg through `urmet-sdk` and originates a
   WebRTC leg for the browser. It exposes an HTTP and WebSocket contract on port
   `8099` and runs `host_network: true` so the browser can reach its media leg over
   ICE host candidates on the LAN.
2. **Integration: Portier Urmet** (`custom_components/urmet/`). A HACS-installable
   custom integration (domain `urmet`, `local_push`). It talks HTTP and WebSocket to
   the add-on, publishes the doorphone entities, services and repairs, and registers
   the card.
3. **Card: `custom:urmet-portier-card`** (`card/`). A Lit + TypeScript Lovelace card
   that owns the WebRTC leg, the ring banner, the openers and the two-way audio. It
   is built by CI and shipped inside the integration.

Install order on the box: add the add-on repository, install and start the add-on,
then add the HACS repository, install the integration, then push the dashboard and
automations. Full steps live in `docs/install.md`.

## Development

The repository is three areas that never trip over each other, each with its own
interpreter and its own config: `gateway` (`.venv`), `integration` (`.venv-ha`),
`card` (`card/`).

```
make build       # provision all three: the gateway .venv (vendored SDK + gateway
                 # package + tooling), the integration .venv-ha (Home Assistant +
                 # the test harness), and the card npm deps
make check       # the unified gate: gateway + integration + card, fail on any
make gateway     # gateway only:     ruff + mypy + pytest        (.venv)
make integration # integration only: ruff + mypy + pytest        (.venv-ha)
make card        # card only:        tsc --noEmit + vitest + rollup bundle
```

The integration uses its own ruff and mypy config under `qa/` (Home Assistant does
not re-export every `websocket_api` name, so mypy runs with `implicit_reexport`).
The card build writes the bundle straight to `custom_components/urmet/www/`, the one
path the integration serves and the release ships.

The gateway is written on top of `urmet-sdk`, pinned as the git submodule at
`addon/urmet-gateway/vendor/urmet-sdk`. Clone with `--recurse-submodules`, or run
`git submodule update --init` after cloning. `urmet-web` is read as evidence and
never copied.

## Layout

- `addon/urmet-gateway/urmet_gateway/` is the gateway package, layered inward:
  `main -> http -> usecases -> domain`, with `sip` and `media` feeding `usecases`.
  The dependency rule is enforced by ruff: `usecases` and `domain` can never import
  `aiohttp`, `aiortc`, `av` or `pjsua2`.
- `tests/` holds full-scenario tests only, driven through the public surface against
  the `urmet_sdk.testing` doubles. No network, no `pjsua2`, no `ffmpeg` except one
  test. `tests/isolation.py` fails the suite if either boundary is crossed.

License: `LicenseRef-FSL-1.1-MIT` (see `LICENSE`).
