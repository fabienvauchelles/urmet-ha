import { css, html, LitElement, type TemplateResult } from "lit";
import {
  AUTO_START_MODES,
  DEFAULT_AUTO_START,
  type HomeAssistant,
  type UrmetCardConfig,
} from "./state";

// A small, dependency-free config editor: entry_id, auto_start, preview_camera
// and the tech-panel toggle. Every change emits a config-changed event with the
// merged config, the contract HA's card editor expects.
export class UrmetPortierCardEditor extends LitElement {
  static properties = {
    _config: { state: true },
  };

  _config: UrmetCardConfig = { type: "custom:urmet-portier-card" };
  hass?: HomeAssistant;

  static styles = css`
    .form {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 8px 0;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.85rem;
      color: var(--secondary-text-color, #727272);
    }
    label.row {
      flex-direction: row;
      align-items: center;
      gap: 8px;
    }
    input,
    select {
      font: inherit;
      padding: 6px 8px;
    }
  `;

  setConfig(config: UrmetCardConfig): void {
    this._config = { ...config };
  }

  private _emit(patch: Partial<UrmetCardConfig>): void {
    this._config = { ...this._config, ...patch };
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      }),
    );
  }

  render(): TemplateResult {
    const config = this._config;
    return html`
      <div class="form">
        <label>
          entry_id (optionnel quand un seul portier existe)
          <input
            .value=${config.entry_id ?? ""}
            @change=${(event: Event) =>
              this._emit({ entry_id: (event.target as HTMLInputElement).value || undefined })}
          />
        </label>
        <label>
          auto_start
          <select
            @change=${(event: Event) =>
              this._emit({
                auto_start: (event.target as HTMLSelectElement)
                  .value as UrmetCardConfig["auto_start"],
              })}
          >
            ${AUTO_START_MODES.map(
              (option) =>
                html`<option value=${option} ?selected=${(config.auto_start ?? DEFAULT_AUTO_START) === option}>
                  ${option}
                </option>`,
            )}
          </select>
        </label>
        <label>
          preview_camera
          <input
            placeholder="camera.your_door_camera (optional)"
            .value=${config.preview_camera ?? ""}
            @change=${(event: Event) =>
              this._emit({ preview_camera: (event.target as HTMLInputElement).value })}
          />
        </label>
        <label class="row">
          <input
            type="checkbox"
            .checked=${config.show_tech ?? true}
            @change=${(event: Event) => this._emit({ show_tech: (event.target as HTMLInputElement).checked })}
          />
          Panneau technique
        </label>
      </div>
    `;
  }
}
