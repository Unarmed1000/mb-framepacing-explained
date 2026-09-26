// The menu after the viewing guide: take the blind test first, or step through the previous results (when this browser has
// any), then start the explanation (its first slide).

import { loadHistory } from "./blind-test/result";
import { showResultHistory } from "./blind-test/test-slide";
import { loadClips, questions } from "./blind-test/trials";
import { missingClips } from "./blind-test/warmup";
import { EXPLANATION_SLIDES } from "./explain/slides";
import type { Slide } from "./slides";

export const menuSlide: Slide = {
  id: "menu",
  title: "Menu",
  render() {
    const body = document.createElement("div");
    body.className = "slide-body";
    renderMenu(body);
    // The menu is rendered once and kept: show it afresh on every visit, so a result just taken is listed
    window.addEventListener("hashchange", () => {
      if (location.hash === "#/menu") renderMenu(body);
    });
    return body;
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
        <p class="previous-note"></p>
      </div>
      <div class="card menu-card">
        <h2>How it works</h2>
        <p>What the test shows and how games get it right: ${EXPLANATION_SLIDES.length} slides with diagrams and live video.</p>
        <a class="button" href="#/${EXPLANATION_SLIDES[0]?.id ?? ""}">Start the explanation →</a>
      </div>
    </div>`;
  const history = loadHistory();
  const previous = body.querySelector<HTMLButtonElement>('[data-action="previous"]')!;
  const note = body.querySelector(".previous-note")!;
  if (history.length === 0) {
    previous.disabled = true;
    note.textContent = "No results yet in this browser: they appear here after the test.";
  } else {
    note.textContent = `${history.length} result${history.length === 1 ? "" : "s"} kept in this browser only.`;
    previous.addEventListener("click", () => {
      loadClips().then(
        (library) => showResultHistory(body, library, history, history.length - 1, () => renderMenu(body)),
        (error: unknown) => body.replaceChildren(missingClips(error)),
      );
    });
  }
}
