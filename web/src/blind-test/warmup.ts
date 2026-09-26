// The warm-up practice slide: one easy pair (a perfect 60 against a ±5 ms window, fast movement), answered, then revealed.

import type { ModeEntry, VideoEntry } from "../manifest";
import { PixelVideo } from "../video/pixel-video";
import { answerBar, DEFINITION, QUESTION, revealCard } from "./reveal";
import { buildWarmup, loadClips, type ClipLibrary } from "./trials";

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

export function warmupSlide(): HTMLElement {
  const slide = document.createElement("div");
  slide.className = "slide-body trial";
  slide.innerHTML = `
    <p class="eyebrow">Practice · warm-up</p>
    <h1></h1>
    <p class="lead"></p>
    <div class="trial-stage"></div>`;
  slide.querySelector("h1")!.textContent = QUESTION;
  slide.querySelector(".lead")!.textContent = `${DEFINITION} This first one is easy to spot.`;
  const stage = slide.querySelector<HTMLDivElement>(".trial-stage")!;
  loadClips().then(
    (library) => practice(stage, library),
    (error: unknown) => stage.replaceChildren(missingClips(error)),
  );
  return slide;
}

function practice(stage: HTMLDivElement, library: ClipLibrary): void {
  const trial = buildWarmup(library, Math.random);
  const { folder, video } = trial.clip;
  const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
  const reveal = document.createElement("div");
  const bar = answerBar((answer) => {
    bar.disable(answer);
    const actions = document.createElement("div");
    actions.className = "actions";
    actions.innerHTML = `
      <button type="button" class="button ghost">Another warm-up</button>
      <a class="button" href="#/blind-test">Next: the blind test →</a>`;
    actions.querySelector("button")!.addEventListener("click", () => {
      player.pause();
      practice(stage, library);
    });
    const card = revealCard(trial, answer, { ...player.health }, player);
    card.append(actions);
    reveal.replaceChildren(card);
  });
  stage.replaceChildren(player.element, bar.element, player.readout, reveal);
  player.play();
}
