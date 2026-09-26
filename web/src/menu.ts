// The menu after the viewing guide: take the blind test first, or step through the previous results (when this browser has
// any), then start the explanation (its first slide), or go straight to measuring animation error.

import { loadHistory } from "./blind-test/result";
import { showResultHistory } from "./blind-test/test-slide";
import { loadClips, questions } from "./blind-test/trials";
import { missingClips } from "./blind-test/warmup";
import { EXPLANATION_SLIDES } from "./explain/slides";
import type { Slide } from "./slides";

const body = document.createElement("div");
body.className = "slide-body";
// Whether the results view was opened from the menu in this visit: then Back to the menu is the browser's Back
let openedFromMenu = false;

/** #/menu: the menu, shown afresh on every visit (so a result just taken is listed); #/menu/results/N: saved result N (oldest
 * first; the latest without N), with its own address so the browser's Back returns to the menu. */
export const menuSlide: Slide = {
  id: "menu",
  title: "Menu",
  render: () => body,
  route(path) {
    const [view, number] = path.split("/");
    if (view !== "results") {
      openedFromMenu = false;
      renderMenu(body);
      return;
    }
    const saved = loadHistory();
    if (saved.length === 0) {
      location.replace("#/menu");
      return;
    }
    const index =
      number === undefined ? saved.length - 1 : Math.min(saved.length - 1, Math.max(0, Number.parseInt(number, 10) || 0));
    loadClips().then(
      (library) =>
        showResultHistory(
          body,
          library,
          saved,
          index,
          () => (openedFromMenu ? history.back() : (location.hash = "#/menu")),
          (to) => location.replace(`#/menu/results/${to}`),
        ),
      (error: unknown) => body.replaceChildren(missingClips(error)),
    );
  },
};

function renderMenu(body: HTMLElement): void {
  body.innerHTML = `
    <p class="eyebrow">Ready</p>
    <h1>Where to next?</h1>
    <p class="lead">Take the blind test before the explanation: it shows what the test is about, so reading it first gives the
      answers away.</p>
    <div class="menu">
      <div class="card menu-card">
        <h2>Blind test</h2>
        <p>A warm-up, then ${questions().length} pairs of moving boxes: which one moves more smoothly?</p>
        <div class="menu-actions">
          <a class="button" href="#/warm-up">Take the test →</a>
          <button type="button" class="button ghost" data-action="previous">Previous results</button>
        </div>
      </div>
      <div class="card menu-card">
        <h2>How it works</h2>
        <p>What the test shows and how games get it right, topic by topic, with diagrams and live video.</p>
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
  const history = loadHistory();
  const previous = body.querySelector<HTMLButtonElement>('[data-action="previous"]')!;
  if (history.length === 0) previous.disabled = true;
  else {
    previous.addEventListener("click", () => {
      openedFromMenu = true;
      location.hash = `#/menu/results/${history.length - 1}`;
    });
  }
}
