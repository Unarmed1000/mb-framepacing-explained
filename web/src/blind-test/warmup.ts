// The jitter test's warm-up pairs (a perfect 60 against a ±5 ms window, fast movement), and the message for missing clips.

import type { ModeEntry, VideoEntry } from "../manifest";

/** How to generate the clips, for when they are missing. */
export const GENERATE = "python tools/web_export/build_blind_test.py";

/** A warm-up pair: a perfect 60 (the ideal timer) on top or bottom, the other half a 60 Hz naive timer in a ±N ms window; the
 * single box at fast speed, never the rows. */
export function isWarmup(video: VideoEntry): boolean {
  if (video.scene !== "box" || video.speed !== "fast") return false;
  const easy = (mode: ModeEntry): boolean => mode.rate === 60 && mode.timer === "naive" && mode.noise === "window";
  const perfect = (mode: ModeEntry): boolean => mode.rate === 60 && mode.timer === "ideal";
  return (perfect(video.top) && easy(video.bottom)) || (easy(video.top) && perfect(video.bottom));
}

/** A message card for when the clips cannot be loaded. */
export function missingClips(error: unknown): HTMLElement {
  const card = document.createElement("div");
  card.className = "card notice";
  card.innerHTML = `<h2>The clips are missing</h2><p></p><pre></pre>`;
  card.querySelector("p")!.textContent = `${String(error)}. Generate them from the repository root:`;
  card.querySelector("pre")!.textContent = GENERATE;
  return card;
}
