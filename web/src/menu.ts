// The menu after the viewing guide: take the blind test first (its picker, with the previous results), then start the
// explanation (its first slide), or go straight to measuring animation error.

import { DEFINITIONS, questions, testById } from "./blind-test/trials";
import { EXPLANATION_SLIDES } from "./explain/slides";
import type { Slide } from "./slides";

const body = document.createElement("div");
body.className = "slide-body";

/** #/menu: the menu. A saved result's old address (#/menu/results/N) now opens the test picker, where each test lists its
 * own. */
export const menuSlide: Slide = {
  id: "menu",
  title: "Menu",
  render: () => body,
  route(path) {
    if (path.split("/")[0] === "results") {
      location.replace("#/blind-test");
      return;
    }
    renderMenu(body);
  },
};

function renderMenu(body: HTMLElement): void {
  body.innerHTML = `
    <p class="eyebrow">Ready</p>
    <h1>Where to next?</h1>
    <p class="lead">Take the blind tests before the explanation: they show what the tests are about, so reading it first gives the
      answers away.</p>
    <div class="menu">
      <div class="card menu-card">
        <h2>Blind tests</h2>
        <p>Pairs of moving boxes: which one moves more smoothly? Two tests, one for each cause of stutter: jitter
          (${questions(DEFINITIONS, testById("jitter")).length + 1} questions) and late frames
          (${questions(DEFINITIONS, testById("late-frames")).length + 1} questions).</p>
        <div class="menu-actions">
          <a class="button" href="#/blind-test">Take the tests →</a>
        </div>
      </div>
      <div class="card menu-card">
        <h2>How it works</h2>
        <p>What the test shows and how apps and games get it right, topic by topic, with diagrams and live video.</p>
        <div class="menu-actions">
          <a class="button" href="#/${EXPLANATION_SLIDES[0]?.id ?? ""}">Start the explanation →</a>
        </div>
      </div>
      <div class="card menu-card">
        <h2>Measure it</h2>
        <p>Animation error, the one number that catches stutter, and how to measure it on a real display with mb-framepacing.</p>
        <div class="menu-actions">
          <a class="button" href="#/measure">Animation error and how to measure it →</a>
        </div>
      </div>
    </div>`;
}
