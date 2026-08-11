import { html, type TemplateResult } from "lit";

// The mic is never opened without an explicit gesture, and when the page is not
// a secure context getUserMedia cannot run, so the talk control degrades to a
// single sentence rather than failing silently (DESIGN 2.3, 7.3, risk 6).
// Listening and watching still work in that case.

export interface TalkOpts {
  secure: boolean;
  talking: boolean;
  available: boolean;
  onToggle: () => void;
}

export function renderTalk(opts: TalkOpts): TemplateResult {
  if (!opts.secure) {
    return html`
      <div class="talk talk-insecure">
        <p>
          Le micro demande une origine sécurisée: utilisez l'application mobile ou l'adresse HTTPS.
          L'écoute et l'image restent disponibles.
        </p>
      </div>
    `;
  }
  return html`
    <div class="talk">
      <button
        class="btn ${opts.talking ? "btn-talk-on" : ""}"
        ?disabled=${!opts.available}
        @click=${opts.onToggle}
      >
        ${opts.talking ? "Couper le micro" : "Parler"}
      </button>
    </div>
  `;
}
