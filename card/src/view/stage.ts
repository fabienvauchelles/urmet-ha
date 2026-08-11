import { html, nothing, type TemplateResult } from "lit";
import { ref, type Ref } from "lit/directives/ref.js";

// The video element lives behind a ref and is always present in the template so
// a hass tick on an unrelated entity can never re-declare it; its srcObject is
// assigned imperatively by the card (DESIGN 7.3, best-practices-card section 2).
// It starts muted autoplay playsinline to clear the autoplay policy; unmuting is
// a separate, gesture-driven talk path.

export interface StageOpts {
  videoRef: Ref<HTMLVideoElement>;
  hasRemote: boolean;
  cameraUrl?: string;
  sentence?: string;
}

export function renderStage(opts: StageOpts): TemplateResult {
  return html`
    <div class="stage">
      <video
        ${ref(opts.videoRef)}
        class="stage-video"
        ?hidden=${!opts.hasRemote}
        muted
        autoplay
        playsinline
      ></video>
      ${!opts.hasRemote && opts.cameraUrl
        ? html`<img class="stage-preview" src=${opts.cameraUrl} alt="Aperçu du portail" />`
        : nothing}
      ${!opts.hasRemote && !opts.cameraUrl
        ? html`<div class="stage-empty">Aperçu indisponible</div>`
        : nothing}
      ${opts.sentence ? html`<div class="stage-note">${opts.sentence}</div>` : nothing}
    </div>
  `;
}
