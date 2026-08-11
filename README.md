# urmet-ha

Home Assistant support for an Urmet 2Voice video doorphone: the ring, the video,
two-way audio, and the door and gate, all inside Home Assistant.

This is an unofficial community project. It is not affiliated with, endorsed by,
or supported by Urmet.

## What it is

Three pieces live in this one repository, installed in this order:

1. **Add-on: Urmet doorphone gateway** (`addon/urmet-gateway/`). A Home Assistant
   OS add-on. It terminates the Urmet SIP leg through `urmet-sdk` (pjsua2 under
   it) and originates a WebRTC leg for the browser. HTTP and WebSocket on port
   `8099`, `host_network: true` so the browser can reach its media over ICE host
   candidates on the LAN.
2. **Integration: Portier Urmet** (`custom_components/urmet/`). A HACS-installable
   custom integration (domain `urmet`, `local_push`). It talks to the add-on,
   publishes the doorphone entities and services, raises Repairs issues, and
   registers the card.
3. **Card: `custom:urmet-portier-card`** (`card/`). A Lit and TypeScript Lovelace
   card that owns the WebRTC leg, the ring banner, the openers and the two-way
   audio. It is built by CI and shipped inside the integration.

## Why this exists

An Urmet 2Voice doorphone has no local API. No RTSP, no snapshot URL, no state
query. The only way to see or hear the panel is to be a SIP endpoint on the Urmet
CallMe cloud and hold a live call, and the panel keys its media with SDES-SRTP,
which browsers refuse to offer. So one process in the middle has to speak SIP and
SRTP to the panel and WebRTC to the browser. That process is the add-on. On top of
it, the integration and the card bring the ring, the video, two-way audio, and the
door and the gate into Home Assistant.

## Install

Install in order: the add-on first, the integration second, the dashboard last.
The integration needs the add-on answering, and the dashboard needs the
integration's entities. Full steps are in [`docs/install.md`](docs/install.md).

1. **Add-on.** Settings > Add-ons > Add-on store > Repositories, add this repo's
   URL, then install and start **Urmet doorphone gateway**. Set the Urmet cloud
   email and password in its options. A pre-built `amd64` image is pulled from the
   registry, so there is no local build.
2. **Integration.** HACS > Custom repositories, add this repo as an **Integration**,
   download **Portier Urmet**, then restart Home Assistant Core (a new integration
   is not loaded by a config reload). On restart the running add-on announces
   itself, so Home Assistant offers the doorphone under Settings > Devices &
   Services with nothing to type: confirm it. If it does not show up, add **Portier
   Urmet** by hand there, host `172.30.32.1`, port `8099`.
3. **Dashboard.** Paste [`dashboard/portier.yaml`](dashboard/portier.yaml) into a
   new dashboard's raw configuration editor, in one step. An optional ring
   notification and a test script sit alongside it. See
   [`dashboard/README.md`](dashboard/README.md).

## Constraints worth knowing before you start

These are not bugs. They come from how the doorphone and browsers work.

- **Answering the call stops the ring on the household handsets.** The panel hands
  the call to whoever answers, so grabbing the panel's own picture during a ring
  would silence the wired handsets. The design shows a normal yard camera during
  the ring and reserves the panel's picture for the moment someone chooses to
  talk. Point the automations and the card at your own camera entity.
- **The card needs H.264.** The panel's video is re-encoded to H.264 and the audio
  to PCMA. A browser that does not offer both cannot show the picture or carry the
  voice. Use the Home Assistant mobile companion app or Chrome. Firefox does not
  offer H.264 in this path and the card says so instead of failing silently.
- **Two-way audio needs a secure context.** Browsers open a microphone only on an
  HTTPS origin or on `http://localhost`, never on a plain `http://` LAN tab.
  Listening and watching work anywhere; talking back needs the companion app or
  your own HTTPS URL for Home Assistant. See
  [`docs/install.md`](docs/install.md).
- **There is no still image.** A frame exists only inside a live SIP call. There
  is no snapshot and no per-thumbnail camera, because that would place a real call
  to the doorbell for every frame.
- **A ring is never proof of identity.** The panel identity is asserted by the
  cloud proxy, not authenticated. Never wire an automation that opens the door on
  a ring alone. Opening is always a human action.
- **The gateway never retries an actuator.** On a step-by-step gate a second pulse
  is a reversal, not a repeat. An unacknowledged open is reported as unknown, never
  as failed and never as open.

## Configuration

Nothing is hardcoded. The add-on is configured through its options, and secrets
belong in Home Assistant secrets (`!secret`), not in the options file in clear.

| Option | Meaning |
| --- | --- |
| `email` | Urmet cloud account email. Optional at start; registration waits until it is set. Use `!secret`. |
| `password` | Urmet cloud account password. Use `!secret`. Never logged, never leaves the add-on. |
| `doorphone_mac` | Panel MAC (`00:11:22:33:44:55` or with underscores). Optional: learned from the first ring when empty. |
| `doorphone_name` | Label shown for the panel in Home Assistant. |
| `look_timeout_s` | How long an unwatched "look at the door" call is held before release, 10 to 120 seconds. |
| `log_level` | `debug`, `info`, `warning` or `error`. Use `debug` only while troubleshooting. |

The Urmet cloud credentials are third-party device credentials, not Home Assistant
user credentials. A wrong or missing login does not stop the add-on: it starts,
answers its health check, and the integration turns the failure into a Repairs
issue that names the add-on.

The integration exposes `event.portier_*`, `button.portier_*`,
`binary_sensor.portier_*` and `sensor.portier_*` entities, and the services
`urmet.answer`, `urmet.look`, `urmet.open`, `urmet.hang_up` and
`urmet.set_microphone`.

## Status and limitations

Version `0.1.1`. Working, early, and honest about what is proven.

- **amd64 only.** The pjsua2 build the add-on relies on is validated for that
  architecture alone.
- **The panel media path is new ground.** The audio tap and the video recorder on
  a live call are the least proven part. Audio-only is the proven fallback and
  keeps working when a picture does not.
- The reverse-engineered protocol details that make this work at all, and the traps
  that cost the most to rediscover, are written down in
  [`docs/protocol-traps.md`](docs/protocol-traps.md). The open hardware questions
  are in [`docs/hardware-test-plan.md`](docs/hardware-test-plan.md).

## Development

Three areas, each with its own interpreter and config: `gateway` (`.venv`),
`integration` (`.venv-ha`), `card` (`card/`).

```
make build       # provision all three: gateway .venv, integration .venv-ha, card npm deps
make check       # unified gate: gateway + integration + card, fail on any
make gateway     # gateway only:     ruff + mypy + pytest        (.venv)
make integration # integration only: ruff + mypy + pytest        (.venv-ha)
make card        # card only:        tsc --noEmit + vitest + rollup bundle
```

The gateway is written on top of [`urmet-sdk`](https://pypi.org/project/urmet-sdk/),
pinned in `addon/urmet-gateway/pyproject.toml` and installed from PyPI. The add-on
image still builds `pjsua2` from source, since that binding is not on PyPI.

The gateway package is layered inward, `main -> http -> usecases -> domain`, with
`sip` and `media` feeding `usecases`. The dependency rule is enforced by ruff:
`usecases` and `domain` can never import `aiohttp`, `aiortc`, `av` or `pjsua2`.
Tests are full-scenario only, driven through the public surface against the
`urmet_sdk.testing` doubles, with no network and no `pjsua2`.

## License

`LicenseRef-FSL-1.1-MIT`, the Functional Source License 1.1 with an MIT future
license. See [`LICENSE`](LICENSE).
