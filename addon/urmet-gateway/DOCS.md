# Urmet doorphone gateway

This add-on terminates the SIP leg of an Urmet CallMe doorphone and originates a
WebRTC leg that a browser can play. A browser cannot talk to the panel directly:
the panel keys its media with SDES-SRTP, which browsers refuse to offer, so one
process in the middle has to speak both sides. That process is this add-on. It
holds `urmet-sdk` (and pjsua2 under it) on the panel side and aiortc on the
browser side.

It is one of three pieces. The other two are the `Portier Urmet` integration
(installed through HACS) and the `custom:urmet-portier-card` Lovelace card. This
add-on is the machine part; you rarely open its page once it runs.

## What it does

- Registers with the Urmet cloud registrar over TLS and stays registered.
- Reports a ring the instant the panel calls, so an automation can put the
  visitor's face on your phone using your existing yard camera. It never answers
  a call on its own.
- On request, answers a ring or places a "look at the door" call, taps the
  panel's audio and video, re-encodes the video to H.264 for the browser, and
  bridges two-way audio.
- Opens the pedestrian door or steps the gate, and reports whether the panel
  acknowledged. An unacknowledged open means the state is unknown, never that the
  door stayed shut.

## Installation

1. Install this add-on from the repository.
2. Open the Configuration tab and set at least the Urmet cloud email and
   password (see Configuration). Save.
3. Start the add-on. Watch the log: it should register within a few seconds.
4. Install the `Portier Urmet` integration through HACS and add it. It talks to
   this add-on over the internal network; the default host is the Supervisor
   bridge gateway `172.30.32.1` on port `8099`.
5. Add the `custom:urmet-portier-card` card to a dashboard.

The install order matters: the add-on first, then the integration, then the
card. `docs/install.md` in the repository covers the dashboard and automations.

## Configuration

| Option | Meaning |
| --- | --- |
| `email` | Urmet cloud account email. Optional at start; registration waits until it is set. Use `!secret`. |
| `password` | Urmet cloud account password. Use `!secret`. Never logged, never leaves the add-on. |
| `doorphone_mac` | Panel MAC (`00:11:22:33:44:55` or with underscores). Optional: learned from the first ring when empty. Set it to register before the first ring. |
| `doorphone_name` | Label shown for the panel in Home Assistant. |
| `look_timeout_s` | How long an unwatched "look" call is held before release, 10 to 120 seconds. |
| `log_level` | `debug`, `info`, `warning` or `error`. Use `debug` only while troubleshooting. |

Credentials are third-party device credentials and belong in the add-on options,
backed by Home Assistant secrets. They are not Home Assistant user credentials.

A wrong or missing cloud login does not stop the add-on. It starts, answers its
health check, and the integration turns the login failure into a Repairs issue
that names this add-on.

## Why host network

The add-on runs on the host network on purpose. The browser reaches the media
leg over ICE host candidates on the LAN, and that media cannot pass through
ingress, which carries only HTTP and WebSocket. The bundled AppArmor profile
compensates: no extra Linux capability, writes confined to the add-on's own data
and tmp directories, and no Home Assistant directory mapped in.

## The diagnostics page

The add-on shows a diagnostics page in the sidebar through ingress. It is the
instrument panel: registration state, live calls and their SIP codes, media
sessions with their packet counters, and the recent event stream. It is
read-only. Everyday control happens through the card and the integration, not
here.

## Two-way audio and secure context

A browser opens a microphone only in a secure context. The Home Assistant
companion apps and an HTTPS origin qualify; a plain `http://` LAN tab does not.
On a plain-http tab the card is listen-only and says so. This is a browser rule,
not an add-on limit.

## Notes and limits

- amd64 only. The pjsua2 build the add-on relies on is validated for that
  architecture alone.
- The panel media path (the audio tap and the video recorder on a live call) is
  new ground; audio-only is the proven fallback and keeps working when a picture
  does not.
- The gateway never retries an actuator. On this gate a second pulse is a
  reversal, not a repeat.
- Answering a ring is always a human action. Answering silences the household
  handsets, so the design shows the yard camera during a ring and reserves the
  panel's own picture for the moment someone chooses to talk.

## Troubleshooting

- **No registration, code 0.** No SIP response reached the add-on. Check the
  cloud email and password, then the Repairs panel.
- **Registered but every call fails with 503.** A stray outbound proxy or Route
  was introduced somewhere upstream. The integration raises a Repairs issue that
  names this exact cause.
- **The panel refuses calls with 486 while idle.** An Urmet firmware or
  vendor-app update may have changed the User-Agent the panel accepts. The
  integration raises a Repairs issue about it.
- **A ring answered but no picture.** The voice still works. The picture path is
  the least proven part; the log records why a picture was given up on.

Set `log_level` to `debug` for a full trace, and back to `info` when done.
