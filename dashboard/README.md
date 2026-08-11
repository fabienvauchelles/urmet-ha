# Portier dashboard, automations and test script

These files are examples you copy into your own Home Assistant configuration. The
integration itself does NOT travel with them: it installs through HACS (see
`../docs/install.md`). Copy each file into your config, merge the two that need
merging, add the `lovelace:` block, then reload or restart as noted below.

## Set your own notify target first

The automations and the test script send to `notify.notify`. Replace that with
your own target before using them, for example `notify.mobile_app_YOUR_PHONE`, or
a notify group if you want the ring to reach several phones. `camera.frontyard` is
an example camera id in the same files and in `portier.yaml`: use your own yard
camera entity.

## Where each file lands

| This file | Lands as | How | Reload |
| --- | --- | --- | --- |
| `portier.yaml` | `dashboards/portier.yaml` (new file) | copy verbatim | see restart note |
| `automations.portier.yaml` | `automations.yaml` | **merge** the list blocks in, keep the existing entries | `automation.reload`, no restart |
| `scripts.portier.yaml` | `scripts.yaml` | **merge** the `portier_test:` key into the dict | `script.reload`, no restart |

`automations.yaml` is a YAML list, so append the five `- id:` blocks.
`scripts.yaml` is a YAML dict, so add the single `portier_test:` key. Do not
overwrite either file.

## The lovelace block (one manual edit in configuration.yaml)

A storage-mode dashboard cannot be shipped as a file, so the Portier dashboard is
declared as a per-dashboard YAML mode entry (this survives the 2026.8 removal of
the top-level `lovelace: mode: yaml` key). Add to `configuration.yaml`:

```yaml
lovelace:
  dashboards:
    portier:
      mode: yaml
      title: Portier
      icon: mdi:doorbell-video
      show_in_sidebar: true
      filename: dashboards/portier.yaml
```

## Restarts needed

A reload of automations and scripts does NOT load a new integration or a new
dashboard. So:

- Adding the `lovelace:` block above needs a **full core restart** (once). The
  dashboard `portier.yaml` file itself needs no further restart after that; edits
  to it are picked up on a dashboard reload or a page refresh.
- The automations and the script need **no restart**: reload them from Developer
  tools > YAML, or call `automation.reload` and `script.reload`.
- The integration (via HACS) needs its own core restart, covered in
  `../docs/install.md`. Order the two restarts so the entities exist before the
  dashboard and automations reference them.

## Deploy order

1. Install and configure the add-on, then the integration via HACS, restart core,
   add the integration through the UI (see `../docs/install.md`). The
   `event.portier_*`, `button.portier_*`, `binary_sensor.portier_*` and
   `sensor.portier_*` entities must exist first.
2. Copy `portier.yaml` into `dashboards/`, merge the automations and the script,
   add the `lovelace:` block.
3. Reload automations and scripts.
4. Full core restart once for the `lovelace:` block.
5. Run `script.portier_test` to put the whole notification chain on the phone.
