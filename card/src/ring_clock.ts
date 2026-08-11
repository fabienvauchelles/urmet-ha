// The elapsed-seconds counter shown while the doorphone rings. It lives beside
// the controller rather than inside it so the controller stays the state machine
// and this stays the one-second tick: it holds the interval, exposes how long the
// ring has run, and asks the host to redraw on each tick.

export class RingClock {
  private timer?: ReturnType<typeof setInterval>;
  private startedAt?: number;
  seconds = 0;

  constructor(private readonly onTick: () => void) {}

  ensure(): void {
    if (this.timer) return;
    this.startedAt = Date.now();
    this.seconds = 0;
    this.timer = setInterval(() => {
      this.seconds = Math.floor((Date.now() - (this.startedAt ?? Date.now())) / 1000);
      this.onTick();
    }, 1000);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
    this.seconds = 0;
    this.startedAt = undefined;
  }
}
