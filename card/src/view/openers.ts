import { html, nothing, type TemplateResult } from "lit";
import type { Actuator } from "../state";

// Door and gate, each behind a two-step confirm. There is deliberately no
// keyboard path: the tiles are click-only elements with no tabindex and no key
// handler, so a physical opener cannot be triggered by a stray Enter or by a
// screen reader's default activation (DESIGN 7.3, risk 9). The gate text names
// the step-by-step reality rather than promising an opening.

export interface OpenerOpts {
  armed: Actuator | null;
  duringRing: boolean;
  onArm: (actuator: Actuator) => void;
  onConfirm: (actuator: Actuator) => void;
  onCancel: () => void;
}

const CONFIRM_TEXT: Record<Actuator, string> = {
  door: "Ouvrir la porte piétonne ?",
  gate: "Portail: un pas de plus (ouvre, stoppe ou ferme selon l'état) ?",
};

const LABEL: Record<Actuator, string> = {
  door: "Ouvrir la porte",
  gate: "Portail",
};

function tile(opts: OpenerOpts, actuator: Actuator): TemplateResult {
  if (opts.armed === actuator) {
    return html`
      <div class="opener armed">
        <span class="opener-confirm-text">${CONFIRM_TEXT[actuator]}</span>
        <div class="opener-confirm-actions">
          <div class="op-btn op-yes" role="button" aria-label="Confirmer" @click=${() => opts.onConfirm(actuator)}>
            Confirmer
          </div>
          <div class="op-btn op-no" role="button" aria-label="Annuler" @click=${opts.onCancel}>Annuler</div>
        </div>
      </div>
    `;
  }
  return html`
    <div class="opener" role="button" aria-label=${LABEL[actuator]} @click=${() => opts.onArm(actuator)}>
      <span>${LABEL[actuator]}</span>
    </div>
  `;
}

export function renderOpeners(opts: OpenerOpts): TemplateResult {
  return html`
    <div class="openers">
      ${opts.duringRing
        ? html`<p class="openers-note">
            Ouvrir pendant une sonnerie prend l'appel: les combinés de la maison cessent de sonner.
          </p>`
        : nothing}
      <div class="openers-row">${tile(opts, "door")} ${tile(opts, "gate")}</div>
    </div>
  `;
}
