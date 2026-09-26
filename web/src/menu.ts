// The menu after the viewing guide: take the blind test, look at a previous result (when this browser has one), or go straight
// to one of the explanation slides.

import { loadHistory } from "./blind-test/result";
import { showSavedResult } from "./blind-test/test-slide";
import { loadClips, questions } from "./blind-test/trials";
import { missingClips } from "./blind-test/warmup";
import { EXPLANATION_SLIDES } from "./explain/slides";
import type { Slide } from "./slides";

/** How many of the latest results the menu offers. */
const PREVIOUS_SHOWN = 5;

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
    <p class="lead">Take the blind test before reading the articles: they explain what it shows, so reading them first gives its
      answers away.</p>
    <div class="menu">
      <div class="card menu-card">
        <h2>Blind test</h2>
        <p>A warm-up, then ${questions().length} pairs of moving boxes: which one moves more smoothly?</p>
        <a class="button" href="#/warm-up">Take the test →</a>
      </div>
      <div class="card menu-card">
        <h2>Previous results</h2>
        <p class="previous-note"></p>
        <div class="previous"></div>
      </div>
      <div class="card menu-card">
        <h2>Articles</h2>
        <ol class="articles"></ol>
      </div>
    </div>`;
  const history = loadHistory().slice(-PREVIOUS_SHOWN).reverse();
  const note = body.querySelector(".previous-note")!;
  const previous = body.querySelector(".previous")!;
  if (history.length === 0) {
    note.textContent = "None yet in this browser: your results appear here after the test.";
    previous.append(
      Object.assign(document.createElement("button"), {
        type: "button",
        className: "button ghost",
        disabled: true,
        textContent: "Show a result",
      }),
    );
  } else {
    note.textContent = "Kept in this browser only. Open one to see its score and watch its questions again.";
    history.forEach((record, index) => {
      const { correct, of } = record.score.overall;
      const button = Object.assign(document.createElement("button"), {
        type: "button",
        className: index === 0 ? "button" : "button ghost",
        textContent: `${index === 0 ? "Latest · " : ""}${record.date} · ${correct} of ${of} right`,
      });
      button.addEventListener("click", () => {
        loadClips().then(
          (library) => showSavedResult(body, library, record, () => renderMenu(body)),
          (error: unknown) => body.replaceChildren(missingClips(error)),
        );
      });
      previous.append(button);
    });
  }
  const articles = body.querySelector(".articles")!;
  for (const slide of EXPLANATION_SLIDES) {
    const link = Object.assign(document.createElement("a"), { href: `#/${slide.id}`, textContent: slide.title });
    const item = document.createElement("li");
    item.append(link);
    articles.append(item);
  }
}
