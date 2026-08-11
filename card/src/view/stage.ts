import { html, nothing, type TemplateResult } from "lit";
import { type Ref, ref } from "lit/directives/ref.js";

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
      ${
        !opts.hasRemote && opts.cameraUrl
          ? html`<img class="stage-preview" src=${opts.cameraUrl} alt="Aperçu du portail" />`
          : nothing
      }
      ${
        !opts.hasRemote && !opts.cameraUrl
          ? html`<div class="stage-empty">
            <svg class="stage-empty-icon" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="7" y="2.5" width="10" height="19" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.3" />
              <circle cx="12" cy="8" r="2" fill="currentColor" />
              <rect x="10" y="13" width="4" height="1.5" rx="0.75" fill="currentColor" />
            </svg>
          </div>`
          : nothing
      }
      ${opts.sentence ? html`<div class="stage-note">${opts.sentence}</div>` : nothing}
    </div>
  `;
}
