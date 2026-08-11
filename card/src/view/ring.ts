import { html, nothing, type TemplateResult } from "lit";

// The ring banner takes over the top of the card during a live ring. It offers
// exactly two actions: Décrocher answers the dialog, Ignorer only dismisses the
// banner locally and never sends anything, so the household handsets keep
// ringing (DESIGN 7.3, EARLY-MEDIA-VERDICT). The preview is the front camera,
// never a SIP call: seeing who is there costs nothing and disturbs nothing.

export interface RingOpts {
  name: string;
  seconds: number;
  cameraUrl?: string;
  onAnswer: () => void;
  onIgnore: () => void;
}

export function renderRing(opts: RingOpts): TemplateResult {
  return html`
    <div class="ring" role="alert" aria-live="assertive">
      <div class="ring-head">
        <span class="ring-dot"></span>
        <span class="ring-title">${opts.name} sonne</span>
        <span class="ring-timer">${opts.seconds}s</span>
      </div>
      ${
        opts.cameraUrl
          ? html`<img class="ring-preview" src=${opts.cameraUrl} alt="Aperçu du portail" />`
          : nothing
      }
      <div class="ring-actions">
        <button class="btn btn-answer" @click=${opts.onAnswer}>Décrocher</button>
        <button class="btn btn-ignore" @click=${opts.onIgnore}>Ignorer</button>
      </div>
      <p class="ring-note">
        Ignorer laisse les combinés de la maison sonner. Décrocher prend l'appel et les combinés
        cessent de sonner.
      </p>
    </div>
  `;
}
