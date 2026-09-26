// The blind test: an intro, the warm-up then the questions in random order, and the results, whose rows fold out to show each
// trial's video again with its reveal; a saved result can be shown the same way.

import { latestViewingReport, overall } from "../checks/viewing";
import { PixelVideo } from "../video/pixel-video";
import { answerBar, DEFINITION, preferenceTally, QUESTION, revealCard, verdict } from "./reveal";
import {
  buildRecord,
  downloadRecord,
  hashText,
  loadHistory,
  restoreAnswers,
  saveToHistory,
  type AnsweredTrial,
  type ResultRecord,
} from "./result";
import { buildRun, loadClips, questions, type Category, type ClipLibrary, type Trial } from "./trials";
import { missingClips } from "./warmup";

const CATEGORIES: Record<Category, { name: string; meaning: string }> = {
  "warm-up": { name: "Warm-up", meaning: "An easy one, to calibrate your eye." },
  pacing: { name: "Pacing", meaning: "The same frame rate, one box with a jittery timer: the stutter this page is about." },
  "frame-rate": { name: "Frame rate", meaning: "A 60 against a 30: the 60 is smoother, even when both are evenly paced." },
  identical: { name: "Identical clips", meaning: "The same clip twice: most people see a difference that is not there." },
  preference: {
    name: "Preference",
    meaning: "Each has a different weakness: not scored; your choices per movement, as the answer can change with the speed.",
  },
};

export function blindTestSlide(): HTMLElement {
  const slide = document.createElement("div");
  slide.className = "slide-body trial";
  loadClips().then(
    (library) => intro(slide, library),
    (error: unknown) => slide.replaceChildren(missingClips(error)),
  );
  return slide;
}

function intro(slide: HTMLElement, library: ClipLibrary): void {
  const history = loadHistory();
  const report = latestViewingReport();
  slide.innerHTML = `
    <p class="eyebrow">Blind test</p>
    <h1>${questions().length + 1} questions, one answer each</h1>
    <p class="lead">
      The warm-up first, then ${questions().length} in random order: each pair both ways round and at different speeds. Each pair loops; answer when you are sure. Some pairs are the same clip
      twice, and some have no right answer. Nothing leaves your browser.
    </p>
    <p class="note">
      The badly timed boxes go wrong on nearly every frame, so a few seconds are enough to see it. Each error is the size measured
      in real games, a few milliseconds, but most games have them less often; setups like multi-GPU SLI have been measured with
      errors on nearly every frame (<a href="https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/measured-errors.md"
      target="_blank" rel="noopener">measured in real games ↗</a>).
    </p>
    <p class="setup"></p>
    <p class="history"></p>
    <button type="button" class="button" data-action="start">Start the test</button>`;
  const setup = slide.querySelector<HTMLElement>(".setup")!;
  if (report === null) setup.innerHTML = `The viewing check has not run yet: <a href="#/best-viewing">run it first</a>.`;
  else {
    const status = overall(report);
    setup.textContent =
      status === "ok"
        ? "Viewing check: ready."
        : `Viewing check: ${status === "warn" ? "usable, with warnings" : "problems to fix"}; see Best viewing. Your result will note it.`;
  }
  const last = history.at(-1);
  slide.querySelector(".history")!.textContent = last
    ? `You took the test ${history.length} time${history.length === 1 ? "" : "s"} in this browser; last time ${last.score.overall.correct} of ${last.score.overall.of}.`
    : "";
  slide
    .querySelector('[data-action="start"]')!
    .addEventListener("click", () => question(slide, library, buildRun(library, Math.random), []));
}

function question(slide: HTMLElement, library: ClipLibrary, run: readonly Trial[], answers: AnsweredTrial[]): void {
  const trial = run[answers.length];
  if (!trial) {
    void results(slide, library, answers);
    return;
  }
  const { folder, video } = trial.clip;
  slide.innerHTML = `<p class="eyebrow"></p><h1></h1><p class="lead"></p><div class="trial-stage"></div>`;
  slide.querySelector(".eyebrow")!.textContent =
    `Blind test · question ${answers.length + 1} of ${run.length}${trial.definition.category === "warm-up" ? " · warm-up" : ""}`;
  slide.querySelector("h1")!.textContent = QUESTION;
  slide.querySelector(".lead")!.textContent = DEFINITION;
  const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
  let started = performance.now();
  player.video.addEventListener("playing", () => (started = performance.now()), { once: true });
  const bar = answerBar((answer) => {
    bar.disable(answer);
    const health = { ...player.health };
    player.pause();
    answers.push({ trial, answer, answerMs: performance.now() - started, health });
    setTimeout(() => question(slide, library, run, answers), 250);
  });
  slide.querySelector(".trial-stage")!.replaceChildren(player.element, bar.element, player.readout);
  player.play();
}

async function results(slide: HTMLElement, library: ClipLibrary, answers: AnsweredTrial[]): Promise<void> {
  const record = buildRecord(
    answers,
    latestViewingReport(),
    await hashText(library.manifestText),
    new Date(),
    navigator.userAgent,
  );
  saveToHistory(record);
  const actions = renderResults(slide, answers, record, "Blind test · result");
  actions.innerHTML = `
    <a class="button" href="#/two-clocks">Next: what you just saw, explained →</a>
    <a class="button ghost" href="#/menu">Menu</a>`;
  actions.append(...recordButtons(record));
  const again = Object.assign(document.createElement("button"), {
    type: "button",
    className: "button ghost",
    textContent: "Take the test again",
  });
  again.addEventListener("click", () => intro(slide, library));
  actions.append(again);
}

/** A saved result, shown like one just taken (its questions can be watched again), with a way back; a result of an earlier test
 * version, whose clips are gone, only shows its score. */
export function showSavedResult(slide: HTMLElement, library: ClipLibrary, record: ResultRecord, back: () => void): void {
  const answers = restoreAnswers(record, library);
  const eyebrow = `Previous result · ${record.date}`;
  let actions: HTMLElement;
  if (answers) actions = renderResults(slide, answers, record, eyebrow);
  else {
    const { correct, of } = record.score.overall;
    slide.innerHTML = `
      <p class="eyebrow"></p>
      <h1></h1>
      <p class="lead">This result is from an earlier version of the test (version ${record.testVersion}); its questions cannot be
        watched again.</p>
      <div class="result-actions"></div>`;
    slide.querySelector(".eyebrow")!.textContent = eyebrow;
    slide.querySelector("h1")!.textContent = `${correct} of ${of} right`;
    actions = slide.querySelector(".result-actions")!;
  }
  const backButton = Object.assign(document.createElement("button"), {
    type: "button",
    className: "button",
    textContent: "← Back to the menu",
  });
  backButton.addEventListener("click", back);
  actions.replaceChildren(backButton, ...recordButtons(record));
}

/** Download and copy buttons for a result. */
function recordButtons(record: ResultRecord): HTMLButtonElement[] {
  const download = Object.assign(document.createElement("button"), {
    type: "button",
    className: "button ghost",
    textContent: "Download result (JSON)",
  });
  download.addEventListener("click", () => downloadRecord(record));
  const copy = Object.assign(document.createElement("button"), {
    type: "button",
    className: "button ghost",
    textContent: "Copy result",
  });
  copy.addEventListener("click", () => {
    void navigator.clipboard.writeText(JSON.stringify(record, null, 2)).then(() => (copy.textContent = "Copied"));
  });
  return [download, copy];
}

/** The results view: score, categories, viewing summary and a row per question that folds out; returns the (empty) actions bar. */
function renderResults(
  slide: HTMLElement,
  answers: readonly AnsweredTrial[],
  record: ResultRecord,
  eyebrow: string,
): HTMLElement {
  slide.innerHTML = `
    <p class="eyebrow"></p>
    <h1></h1>
    <p class="lead"></p>
    <div class="card categories"></div>
    <p class="setup"></p>
    <h2 class="list-title">Every question</h2>
    <p class="hint">Open a row to watch its pair again, with what each box was and its animation error.</p>
    <div class="trial-list"></div>
    <div class="result-actions"></div>`;
  slide.querySelector(".eyebrow")!.textContent = eyebrow;
  const { overall: total, byCategory } = record.score;
  slide.querySelector("h1")!.textContent = `${total.correct} of ${total.of} right`;
  slide.querySelector(".lead")!.textContent =
    "Scored: the warm-up, the pacing, frame rate and identical-clip questions. The preference questions have no right answer.";
  const categories = slide.querySelector(".categories")!;
  for (const category of ["warm-up", "pacing", "frame-rate", "identical", "preference"] as const) {
    const row = document.createElement("div");
    row.className = "category-row";
    const scored = byCategory[category];
    const value = scored ? `${scored.correct} of ${scored.of}` : "Not scored";
    row.innerHTML = `<span class="category-name"></span><span class="category-score"></span><span class="category-meaning"></span>`;
    row.querySelector(".category-name")!.textContent = CATEGORIES[category].name;
    row.querySelector(".category-score")!.textContent = value;
    row.querySelector(".category-meaning")!.textContent = CATEGORIES[category].meaning;
    if (category === "preference") {
      const tally = document.createElement("ul");
      tally.className = "tally";
      for (const line of preferenceTally(answers))
        tally.append(Object.assign(document.createElement("li"), { textContent: line }));
      row.querySelector(".category-meaning")!.append(tally);
    }
    categories.append(row);
  }
  slide.querySelector(".setup")!.textContent = viewingSummary(record);
  const list = slide.querySelector(".trial-list")!;
  for (const answered of answers) list.append(foldOut(answered));
  return slide.querySelector(".result-actions")!;
}

function viewingSummary(record: ResultRecord): string {
  const viewing = record.viewing;
  const flagged = record.trials.filter(
    (trial) => trial.playback.presented > 0 && trial.playback.offRhythm / trial.playback.presented > 0.02,
  );
  const refresh = viewing?.refreshHz
    ? `${viewing.refreshHz} Hz${viewing.sixtyMultiple ? "" : " (not a multiple of 60)"}`
    : "unknown";
  const scale = viewing ? `, scale ${Math.round(viewing.devicePixelRatio * 100)} %` : "";
  const note = flagged.length ? ` Playback looked uneven in ${flagged.length} question${flagged.length === 1 ? "" : "s"}.` : "";
  return `Taken at ${refresh}${scale}.${note}`;
}

/** A result row that folds out to the trial's video, reveal and chart; the video only plays while the row is open. */
function foldOut({ trial, answer, health }: AnsweredTrial): HTMLElement {
  const row = document.createElement("details");
  row.className = "trial-row";
  const summary = document.createElement("summary");
  summary.innerHTML = `<span class="trial-number"></span><span class="trial-kind"></span><span class="trial-verdict"></span>`;
  summary.querySelector(".trial-number")!.textContent = String(trial.position + 1);
  summary.querySelector(".trial-kind")!.textContent = `${CATEGORIES[trial.definition.category].name} · ${trial.motion} movement`;
  const verdictText = verdict(trial, answer);
  const verdictElement = summary.querySelector<HTMLElement>(".trial-verdict")!;
  verdictElement.textContent = verdictText;
  verdictElement.dataset.kind = verdictText === "Correct" ? "correct" : trial.definition.smoother === null ? "choice" : "wrong";
  row.append(summary);
  let player: PixelVideo | null = null;
  row.addEventListener("toggle", () => {
    if (row.open) {
      if (!player) {
        const { folder, video } = trial.clip;
        player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
        row.append(player.element, player.readout, revealCard(trial, answer, health, player));
      }
      player.play();
    } else player?.pause();
  });
  return row;
}
