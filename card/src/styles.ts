import { css } from "lit";

// Tokens map onto Home Assistant theme variables with fallbacks, so the card
// follows the active theme without fighting card-mod's injected styles
// (best-practices-card section 2).
export const cardStyles = css`
  :host {
    --urmet-fg: var(--primary-text-color, #212121);
    --urmet-muted: var(--secondary-text-color, #727272);
    --urmet-accent: var(--primary-color, #1e88e5);
    --urmet-danger: var(--error-color, #db4437);
    --urmet-ok: var(--success-color, #43a047);
    --urmet-line: var(--divider-color, #e0e0e0);
    display: block;
  }
  ha-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    color: var(--urmet-fg);
  }
  .banner {
    background: var(--urmet-danger);
    color: #fff;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.9rem;
  }
  .ring {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--urmet-accent);
    color: #fff;
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ring-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }
  .ring-title {
    flex: 1;
  }
  .ring-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #fff;
    animation: urmet-pulse 1s infinite;
  }
  @keyframes urmet-pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.3;
    }
  }
  .ring-preview,
  .stage-preview,
  .stage-video {
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    background: #000;
    border-radius: 8px;
    display: block;
  }
  .ring-actions {
    display: flex;
    gap: 8px;
  }
  .ring-note {
    margin: 0;
    font-size: 0.8rem;
    opacity: 0.9;
  }
  .stage {
    position: relative;
  }
  .stage-video[hidden] {
    display: none;
  }
  .stage-note {
    position: absolute;
    left: 8px;
    bottom: 8px;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.85rem;
  }
  .stage-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 4 / 3;
    background: var(--urmet-line);
    color: var(--urmet-muted);
    border-radius: 8px;
  }
  .stage-empty-icon {
    width: 28%;
    max-width: 88px;
    height: auto;
    opacity: 0.7;
  }
  .btn {
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    flex: 1;
    background: var(--urmet-line);
    color: var(--urmet-fg);
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .btn-answer {
    background: var(--urmet-ok);
    color: #fff;
  }
  .btn-ignore {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
  }
  .btn-hang {
    background: var(--urmet-danger);
    color: #fff;
  }
  .btn-talk-on {
    background: var(--urmet-accent);
    color: #fff;
  }
  .actions,
  .talk {
    display: flex;
    gap: 8px;
  }
  .talk-insecure p {
    margin: 0;
    font-size: 0.85rem;
    color: var(--urmet-muted);
  }
  .tech {
    border-top: 1px solid var(--urmet-line);
    padding-top: 8px;
  }
  .tech-title {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--urmet-muted);
    margin-bottom: 6px;
  }
  .tech-grid {
    display: grid;
    gap: 2px 12px;
    font-size: 0.8rem;
  }
  .tech-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .tech-row span:first-child {
    color: var(--urmet-muted);
  }
`;
