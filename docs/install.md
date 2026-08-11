# Install

Three pieces, installed in this order: the add-on (the SIP gateway), the
integration (through HACS), then the dashboard and automations. Do not reorder:
the integration needs the add-on answering, and the dashboard needs the
integration's entities.

## 1. The add-on

1. Settings > Apps > Add-on store > top-right menu > Repositories. Add
   `https://github.com/fabienvauchelles/urmet-ha` and reload the store.
2. Install **Urmet doorphone gateway**. The pre-built `amd64` image is pulled
   from `ghcr.io/fabienvauchelles/urmet-gateway`, so there is no local build.
3. Configure the options: `email` and `password` (the Urmet cloud account),
   `doorphone_mac`, `doorphone_name`. Leave `look_timeout_s` and `log_level` at
   their defaults.
4. Start the add-on. `boot: auto` keeps it started across reboots.
5. Open the add-on's ingress panel and confirm `GET /api/health` answers
   `{"ok": true}`. The port opens before SIP registration, so health answers
   within about 2 s even while the binding is still coming up.

## 2. The integration (HACS)

The integration is not on the default add-on store. It installs through HACS as a
custom repository.

1. HACS > top-right menu > Custom repositories. Add
   `https://github.com/fabienvauchelles/urmet-ha`, category **Integration**.
2. Download **Portier Urmet**.
3. **Restart Home Assistant Core** (Developer tools > YAML > Restart, or Settings
   > System > Restart). A new integration is not loaded by a config reload.
4. On restart the running add-on announces the gateway through the Supervisor, so
   **Portier Urmet** appears on its own under Settings > Devices & Services, host
   and port already filled. Confirm it.
5. If it does not appear, add it by hand: Add integration > **Portier Urmet**,
   host `172.30.32.1` (the Supervisor bridge gateway, how a Core container reaches
   a `host_network` add-on), port `8099`. The flow reads the doorphone MAC from
   the gateway and keys the entry on it. If it says no panel is known yet, set
   `doorphone_mac` in the add-on options or ring the doorphone once, then confirm.

## 3. The dashboard and automations

`dashboard/portier.yaml` is a whole dashboard you import in one step: Settings >
Dashboards > Add dashboard > New dashboard from scratch, open it, Edit (the
pencil) > the three-dot menu > Raw configuration editor, and paste the file. No
`configuration.yaml` edit and no restart. It is a single `custom:urmet-portier-card`
that finds the doorphone through the integration.

The optional ring notification (`automations.portier.yaml`) and the test script
(`scripts.portier.yaml`) merge into your `automations.yaml` and `scripts.yaml` and
reload with no restart. Set your own `notify` target and yard camera in them first;
full guidance is in `../dashboard/README.md`. Then run `script.portier_test` to put
the whole notification chain on the phone.

## Two-way audio needs a secure context

Listening and watching work anywhere. Talking back does not: the microphone needs
a browser secure context, and a plain `http://` tab on the LAN (for example
`http://homeassistant.local`) is not one. Browsers only expose `getUserMedia` on
`https://` origins and on `http://localhost`, so a LAN hostname over plain HTTP is
refused. The card disables the talk control with a plain sentence rather than
failing silently.

For two-way audio use one of:

- the Home Assistant **companion app** (iOS or Android), which grants the
  microphone natively, or
- your own HTTPS origin for Home Assistant, for example
  `https://home-assistant.example.com`. Use whatever HTTPS URL your instance is
  reachable at (a reverse proxy, Nabu Casa, or a self-signed cert all qualify).

Not `http` on the LAN. This is a browser rule, not a limitation of the gateway.
