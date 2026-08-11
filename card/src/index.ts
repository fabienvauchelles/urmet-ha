import { UrmetPortierCard } from "./card";
import { UrmetPortierCardEditor } from "./editor";

const CARD_TYPE = "urmet-portier-card";
const EDITOR_TYPE = "urmet-portier-card-editor";

if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, UrmetPortierCard);
if (!customElements.get(EDITOR_TYPE)) customElements.define(EDITOR_TYPE, UrmetPortierCardEditor);

interface CustomCardEntry {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

const win = window as unknown as { customCards?: CustomCardEntry[] };
win.customCards = win.customCards ?? [];
win.customCards.push({
  type: CARD_TYPE,
  name: "Portier Urmet",
  description:
    "Answer the Urmet doorphone, watch the gate and open the door or gate from Home Assistant.",
  preview: true,
  documentationURL: "https://github.com/fabienvauchelles/urmet-ha",
});
