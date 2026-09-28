// One switch for every video on the page: a reader who finds the motion distracting while reading pauses them all at once, from
// the top bar or with P, and plays them again the same way. The choice is remembered in this browser; without one, a reader whose
// system asks for reduced motion starts with the videos paused.

const KEY = "mb-framepacing-explained.videos-paused";

/** The reader's earlier choice, or null when there is none (or storage is unavailable). */
function storedChoice(): boolean | null {
  try {
    const stored = localStorage.getItem(KEY);
    return stored === null ? null : stored === "true";
  } catch {
    return null;
  }
}

function prefersReducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

let paused = storedChoice() ?? prefersReducedMotion();
const listeners = new Set<(paused: boolean) => void>();

/** Whether the reader has paused the videos. */
export function videosPaused(): boolean {
  return paused;
}

export function setVideosPaused(value: boolean): void {
  if (value === paused) return;
  paused = value;
  try {
    localStorage.setItem(KEY, String(value));
  } catch {
    // Private windows and blocked storage: the switch still works until the page is closed
  }
  for (const listener of listeners) listener(value);
}

/** Call `listener` whenever the videos are paused or played again. */
export function onVideosPaused(listener: (paused: boolean) => void): void {
  listeners.add(listener);
}

/** The top bar's switch: pauses or plays every video on the page; P does the same anywhere on the page. */
export function motionSwitch(): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "motion-switch";
  button.setAttribute("aria-keyshortcuts", "P");
  // Both labels are always there, on top of each other, and only the current one is visible: the button keeps the width of the
  // longer one, so the top bar does not shift when it changes
  button.innerHTML = `
    <span class="motion-state" data-state="playing"><span aria-hidden="true">⏸</span><span class="motion-label">Pause videos</span></span>
    <span class="motion-state" data-state="paused"><span aria-hidden="true">▶</span><span class="motion-label">Play videos</span></span>`;
  const update = (): void => {
    button.setAttribute("aria-label", paused ? "Play videos" : "Pause videos");
    button.title = paused ? "Play every video on the page (P)" : "Pause every video on the page (P)";
    button.dataset.paused = String(paused);
  };
  button.addEventListener("click", () => setVideosPaused(!paused));
  onVideosPaused(update);
  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "p" || event.key === "P") setVideosPaused(!paused);
  });
  update();
  return button;
}
