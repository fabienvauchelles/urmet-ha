import { LitElement, html, nothing, type TemplateResult } from "lit";
import { createRef, type Ref } from "lit/directives/ref.js";
import { cardStyles } from "./styles";
import { LinkController } from "./controller";
import {
  AUTO_START_MODES,
  DEFAULT_AUTO_START,
  findDoorbellEntity,
  stageSentence,
  statesEqual,
  trackedIds,
  type AutoStart,
  type HomeAssistant,
  type UrmetCardConfig,
} from "./state";
import { renderRing } from "./view/ring";
import { renderStage } from "./view/stage";
import { renderTalk } from "./view/talk";
import { renderTech } from "./view/tech";

const ALLOWED_KEYS = new Set([
  "type",
  "entry_id",
  "auto_start",
  "preview_camera",
  "show_tech",
  "grid_options",
  "layout_options",
  "view_layout",
]);

export class UrmetPortierCard extends LitElement {
  static styles = cardStyles;

  private readonly _link = new LinkController(this);
  private _config?: UrmetCardConfig;
  private _hass?: HomeAssistant;
  private readonly _videoRef: Ref<HTMLVideoElement> = createRef();

  setConfig(config: UrmetCardConfig): void {
    for (const key of Object.keys(config)) {
      if (!ALLOWED_KEYS.has(key)) throw new Error(`Clé de configuration inconnue: ${key}`);
    }
    const mode = config.auto_start ?? DEFAULT_AUTO_START;
    if (!AUTO_START_MODES.includes(mode))
      throw new Error(`auto_start invalide: ${String(config.auto_start)}`);
    this._config = {
      ...config,
      auto_start: mode,
      preview_camera: config.preview_camera,
      show_tech: config.show_tech ?? true,
    };
    this._link.config = this._config;
  }

  set hass(hass: HomeAssistant) {
    const previous = this._hass;
    this._hass = hass;
    const doorbell = findDoorbellEntity(hass, undefined);
    if (!statesEqual(previous, hass, trackedIds(this._config, doorbell))) this.requestUpdate();
    this._link.updateHass(hass);
  }

  get hass(): HomeAssistant | undefined {
    return this._hass;
  }

  getCardSize(): number {
    return 8;
  }

  // Height follows the content: the stage keeps a 4/3 aspect and the actions sit
  // right under it. A fixed row span left a tall empty band below the button on a
  // phone, so the card auto-sizes and only pins its width.
  getGridOptions(): { rows: "auto"; columns: number } {
    return { rows: "auto", columns: 12 };
  }

  static getConfigElement(): HTMLElement {
    return document.createElement("urmet-portier-card-editor");
  }

  static getStubConfig(): { auto_start: AutoStart } {
    return { auto_start: DEFAULT_AUTO_START };
  }

  private _cameraUrl(): string | undefined {
    const entity = this._config?.preview_camera;
    if (!entity) return undefined;
    const token = this._hass?.states[entity]?.attributes["access_token"];
    return typeof token === "string" ? `/api/camera_proxy_stream/${entity}?token=${token}` : undefined;
  }

  private _assignStream(): void {
    const video = this._videoRef.value;
    if (!video) return;
    const next = this._link.stream ?? null;
    if (video.srcObject !== next) {
      video.srcObject = next;
      video.muted = true;
      if (next) {
        try {
          const started = video.play?.();
          if (started)
            void started
              // The panel's voice rides the same stream, so a muted element would
              // show the visitor but never let them be heard. Unmute once the
              // muted autoplay has cleared the policy.
              .then(() => {
                video.muted = false;
              })
              .catch((error) => console.debug("urmet: play rejected", error));
        } catch (error) {
          console.debug("urmet: play threw", error);
        }
      }
    }
  }

  protected updated(): void {
    this._assignStream();
  }

  render(): TemplateResult {
    if (!this._config) return html``;
    const link = this._link;
    if (link.resolveError) {
      return html`<ha-card><div class="banner" role="alert">${link.resolveError}</div></ha-card>`;
    }
    const vm = link.vm;
    const cameraUrl = this._cameraUrl();
    const ringing =
      vm.ringingCall && vm.ringingCall.id !== link.ignoredCallId ? vm.ringingCall : undefined;
    const secure = typeof window !== "undefined" && window.isSecureContext;
    const talkAvailable = link.linkState === "live" || link.linkState === "degraded";
    return html`
      <ha-card>
        ${ringing
          ? renderRing({
              name: vm.doorphoneName,
              seconds: link.ringSeconds,
              cameraUrl,
              onAnswer: () => link.answer(ringing.id),
              onIgnore: () => link.ignore(ringing.id),
            })
          : nothing}
        ${renderStage({
          videoRef: this._videoRef,
          hasRemote: link.hasRemote,
          cameraUrl: link.hasRemote ? undefined : cameraUrl,
          sentence: stageSentence(link.linkState, vm.hasPicture),
        })}
        ${link.error ? html`<div class="banner" role="alert">${link.error}</div>` : nothing}
        ${renderTalk({
          secure,
          talking: link.talking,
          available: talkAvailable,
          onToggle: () => void link.toggleTalk(),
        })}
        ${this._renderActions(link.hasLink, !!ringing)}
        ${this._config.show_tech
          ? renderTech({ vm, linkState: link.linkState, sessionId: link.sessionId })
          : nothing}
      </ha-card>
    `;
  }

  private _renderActions(hasLink: boolean, ringing: boolean): TemplateResult {
    if (hasLink) {
      return html`<div class="actions">
        <button class="btn btn-hang" @click=${() => this._link.hangUp()}>Raccrocher</button>
      </div>`;
    }
    if (ringing) return html``;
    const busy = this._link.linkState === "answering" || this._link.connecting;
    return html`<div class="actions">
      <button class="btn" ?disabled=${busy} @click=${() => this._link.look()}>Regarder</button>
    </div>`;
  }
}
