# Portier dashboard, automations and test script

These files are authored here and copied into the GitOps repository
`/home/fabien/gitrepos/homeassistant`, which is where they are versioned and
deployed. The integration itself does NOT travel through GitOps: it ships through
HACS (`custom_components/` is gitignored on the box). See `../docs/install.md`.

Always run `gitops_push` before editing the box's config, because
`gitops_pull.sh` merges without reset and a pull that refuses to advance means
unversioned drift on the box that must be captured first.

## Where each file lands

| This file | Lands as | How | Reload |
| --- | --- | --- | --- |
| `portier.yaml` | `dashboards/portier.yaml` (new file) | copy verbatim | see restart note |
| `automations.portier.yaml` | `automations.yaml` | **merge** the list blocks in, keep the existing entries | webhook runs `automation.reload`, no restart |
| `scripts.portier.yaml` | `scripts.yaml` | **merge** the `portier_test:` key into the dict | webhook runs `script.reload`, no restart |

`automations.yaml` is a YAML list, so append the five `- id:` blocks.
`scripts.yaml` is a YAML dict, so add the single `portier_test:` key. Do not
overwrite either file.

## The lovelace block (one manual edit in configuration.yaml)

`.storage` is gitignored and a storage-mode dashboard cannot be versioned, so the
Portier dashboard is declared as a per-dashboard YAML mode entry (this survives
the 2026.8 removal of the top-level `lovelace: mode: yaml` key). Add to
`configuration.yaml`:

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

Verify against core 2026.8 whether a `resource_mode: storage` sibling is now
required to keep the HACS-managed Lovelace resource working; add it if so.

## Restarts needed (DESIGN risk 10)

The webhook reload chain reloads automations, scripts, scenes and core config. It
does NOT load a new integration or a new dashboard. So:

- Adding the `lovelace:` block above needs a **full core restart** (once). The
  dashboard `portier.yaml` file itself needs no further restart after that; edits
  to it are picked up on a dashboard reload or a page refresh.
- The automations and the script need **no restart**: push, then fire the deploy
  webhook (or run `gitops_pull.sh` on the box).
- The integration (via HACS) needs its own core restart, covered in
  `../docs/install.md`. Order the two restarts so the entities exist before the
  dashboard and automations reference them.

## Deploy order

1. Install and configure the add-on, then the integration via HACS, restart core,
   add the integration through the UI (see `../docs/install.md`). The
   `event.portier_*`, `button.portier_*`, `binary_sensor.portier_*` and
   `sensor.portier_*` entities must exist first.
2. `gitops_push`, then copy `portier.yaml` into `dashboards/`, merge the
   automations and the script, add the `lovelace:` block.
3. Commit, push, fire the deploy webhook.
4. Full core restart once for the `lovelace:` block.
5. Run `script.portier_test` to put the whole notification chain on the phone.
