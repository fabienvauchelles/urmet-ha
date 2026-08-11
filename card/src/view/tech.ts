import { html, nothing, type TemplateResult } from "lit";
import type { CardViewModel, LinkState } from "../state";

// The instrument panel, always on screen when enabled and never folded: it is
// the surface WP12's script.portier_test exercises before anyone theorises
// about SIP (DESIGN 5.8 trap 12, 7.2). Every reading comes from the pushed
// session state so it cannot drift from what the gateway sees.

export interface TechOpts {
  vm: CardViewModel;
  linkState: LinkState;
  sessionId?: string;
}

function row(key: string, value: string | number): TemplateResult {
  return html`<div class="tech-row"><span>${key}</span><span>${value}</span></div>`;
}

export function renderTech(opts: TechOpts): TemplateResult {
  const session = opts.vm.session;
  const video = session?.video ?? null;
  const audio = session?.audio ?? null;
  const call = opts.vm.activeCall;
  return html`
    <div class="tech">
      <div class="tech-title">Technique</div>
      <div class="tech-grid">
        ${row("Lien", opts.linkState)}
        ${row("Enregistré SIP", opts.vm.registered ? "oui" : "non")}
        ${row("Micro", opts.vm.micMuted ? "coupé" : "ouvert")}
        ${row("Appel", call ? `${call.state} (${call.direction})` : "aucun")}
        ${row("Session", session ? `${session.state} / ${session.connection}` : "aucune")}
        ${row("Image", video ? `${video.width}x${video.height}` : "aucune")}
        ${row(
          "Paquets vidéo",
          video ? `${video.packets_sent} envoyés / ${video.packets_dropped} perdus` : "-",
        )}
        ${row("Audio portier→nav", audio ? `${audio.from_doorphone} → ${audio.to_browser}` : "-")}
        ${row(
          "Audio nav→portier",
          audio ? `${audio.to_doorphone} (silence ${audio.silence_sent})` : "-",
        )}
        ${row(
          "Callback audio",
          audio ? `${audio.max_callback_ms.toFixed(1)} / ${audio.budget_ms.toFixed(1)} ms` : "-",
        )}
        ${opts.sessionId ? row("Session id", opts.sessionId) : nothing}
      </div>
    </div>
  `;
}
