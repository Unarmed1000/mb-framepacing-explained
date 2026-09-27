// The blind test: an intro, the warm-up then the questions in random order, and the results, whose rows fold out to show each
// trial's video again with its reveal; a saved result can be shown the same way.

import { latestViewingReport, overall } from "../checks/viewing";
import { PixelVideo } from "../video/pixel-video";
import {
  answerBar,
  choiceName,
  chosen,
  DEFINITION,
  preferenceTally,
  QUESTION,
  revealCard,
  tallyByMotion,
  verdict,
  verdictText,
} from "./reveal";
import {
  buildRecord,
  downloadRecord,
  hashText,
  loadHistory,
  restoreEach,
  saveToHistory,
  type AnsweredTrial,
  type ResultRecord,
  type TrialRecord,
} from "./result";
import {
  buildRun,
  DEFINITIONS,
  isCorrect,
  isPreference,
  loadClips,
  questions,
  testById,
  buildWarmup,
  warmupOf,
  type Category,
  type ClipLibrary,
  type TestDefinition,
  type Trial,
} from "./trials";
import type { Slide } from "../slides";
import { missingClips } from "./warmup";

const CATEGORIES: Record<Category, { name: string; meaning: string }> = {
  "warm-up": { name: "Warm-up", meaning: "An easy one, to calibrate your eye." },
  pacing: { name: "Pacing", meaning: "The same frame rate, one box with a jittery timer: the stutter this page is about." },
  "late-frames": {
    name: "Late frames",
    meaning:
      "The second cause of stutter: frames that miss their refresh. The smoother box's frames arrive on time, or its rate adapts.",
  },
  "frame-rate": { name: "Frame rate", meaning: "A 60 against a 30: the 60 is smoother, even when both are evenly paced." },
  identical: { name: "Identical clips", meaning: "The same clip twice: most people see a difference that is not there." },
  "late-preference": {
    name: "Preference",
    meaning: "A 60 with late frames against an even 30 or 20: not scored; your choices per movement.",
  },
  preference: {
    name: "Preference",
    meaning: "Each has a different weakness: not scored; your choices per movement, as the answer can change with the speed.",
  },
};

/** The late frames test's reminder with every question: its stutter comes in bursts. */
const WATCH_A_WHOLE_MOVE =
  "Watch at least one whole move, left to right and back, before you answer: late frames come in bursts.";

const body = document.createElement("div");
body.className = "slide-body trial";
// Whether the results view was opened from the picker in this visit: then Back to the tests is the browser's Back
let openedFromPicker = false;

/** A test's saved results, oldest first; results from before there was a choice of test were the jitter test's. */
function resultsOf(test: string): ResultRecord[] {
  return loadHistory().filter((record) => (record.test ?? "jitter") === test);
}

/** #/blind-test: the test picker, shown afresh on every visit (so a result just taken counts); #/blind-test/results/TEST/N: the
 * test's saved result N (oldest first; the latest without N), with its own address so the browser's Back returns to the
 * picker. */
export const blindTestSlide: Slide = {
  id: "blind-test",
  title: "Blind tests",
  render: () => body,
  route(path) {
    const [view, test = "", number] = path.split("/");
    const saved = resultsOf(test);
    if (view !== "results" || saved.length === 0) {
      if (view === "results") location.replace("#/blind-test");
      openedFromPicker = false;
      loadClips().then(
        (library) => intro(body, library),
        (error: unknown) => body.replaceChildren(missingClips(error)),
      );
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
          () => (openedFromPicker ? history.back() : (location.hash = "#/blind-test")),
          (to) => location.replace(`#/blind-test/results/${test}/${to}`),
        ),
      (error: unknown) => body.replaceChildren(missingClips(error)),
    );
  },
};

function intro(slide: HTMLElement, library: ClipLibrary): void {
  const report = latestViewingReport();
  const jitter = testById("jitter");
  const late = testById("late-frames");
  const count = (test: TestDefinition): number => questions(DEFINITIONS, test).length + (test.warmup ? 1 : 0);
  slide.innerHTML = `
    <p class="eyebrow">Blind tests</p>
    <h1>Two blind tests: pick one</h1>
    <p class="lead">
      One for each cause of stutter. Each pair loops; answer when you are sure, one answer each. The questions come in random
      order, each pair both ways round. Nothing leaves your browser.
    </p>
    <div class="guide test-choice">
      <div class="card">
        <h2>Jitter · ${count(jitter)} questions</h2>
        <p>The first cause of stutter: a timer that reads the clock a little early or late, so frames show a slightly wrong
          moment although every one arrives on time. <strong>Harder to spot than late frames.</strong> The warm-up first, then
          ${count(jitter) - 1} at different speeds; some pairs are the same clip twice, and some have no right answer.</p>
        <p class="note">
          Made to be seen in seconds: the badly timed boxes go wrong on nearly every frame. Each error is the size measured in
          real games, a few milliseconds, but most games have them less often; setups like multi-GPU SLI have been measured with
          errors on nearly every frame (<a href="https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/measured-errors.md"
          target="_blank" rel="noopener">measured in real games ↗</a>). The boxes are also drawn on a 2 × 2 pixel grid, like a
          2× zoom, so every step moves twice as many of your screen's pixels.
        </p>
        <div class="choice-actions" data-for="jitter">
          <p class="history"></p>
          <button type="button" class="button" data-test="jitter">Start the jitter test</button>
          <button type="button" class="button ghost" data-previous="jitter">Previous results</button>
        </div>
      </div>
      <div class="card">
        <h2>Late frames · ${count(late)} questions</h2>
        <p>The second cause of stutter: frames that miss their refresh, a whole refresh late, and a game that adapts its rate
          to a busy stretch. A warm-up first, then ${count(late) - 1} at different speeds; some have no right answer.</p>
        <p><strong>Watch at least one whole move, from left to right and back, before you answer:</strong> late frames come
          in bursts, not on every frame, so a quick look can miss them.</p>
        <div class="choice-actions" data-for="late-frames">
          <p class="history"></p>
          <button type="button" class="button" data-test="late-frames">Start the late frames test</button>
          <button type="button" class="button ghost" data-previous="late-frames">Previous results</button>
        </div>
      </div>
    </div>
    <p class="setup"></p>`;
  const setup = slide.querySelector<HTMLElement>(".setup")!;
  if (report === null) setup.innerHTML = `The viewing check has not run yet: <a href="#/best-viewing">run it first</a>.`;
  else {
    const status = overall(report);
    setup.textContent =
      status === "ok"
        ? "Viewing check: ready."
        : `Viewing check: ${status === "warn" ? "usable, with warnings" : "problems to fix"}; see Best viewing. Your result will note it.`;
  }
  // Each test's own results: how often and how it went last time, and a way into them
  for (const actions of slide.querySelectorAll<HTMLElement>(".choice-actions")) {
    const test = actions.dataset["for"]!;
    const saved = resultsOf(test);
    const last = saved.at(-1);
    actions.querySelector(".history")!.textContent = last
      ? `Taken ${saved.length} time${saved.length === 1 ? "" : "s"} in this browser; last time ${last.score.overall.correct} of ${last.score.overall.of}.`
      : "";
    const previous = actions.querySelector<HTMLButtonElement>("[data-previous]")!;
    if (!last) previous.disabled = true;
    else
      previous.addEventListener("click", () => {
        openedFromPicker = true;
        location.hash = `#/blind-test/results/${test}/${saved.length - 1}`;
      });
  }
  for (const button of slide.querySelectorAll<HTMLButtonElement>("[data-test]")) {
    const test = testById(button.dataset["test"]!);
    button.addEventListener("click", () => practice(slide, library, test));
  }
}

/** A test's practice warm-up: an easy pair of its own, answered and revealed, as often as wanted; then the test itself. Not
 * saved or scored (the test starts with a warm-up question of its own). */
function practice(slide: HTMLElement, library: ClipLibrary, test: TestDefinition): void {
  const start = (): void => question(slide, library, test, buildRun(library, Math.random, DEFINITIONS, test), []);
  const warmup = warmupOf(test);
  if (!warmup) {
    start();
    return;
  }
  const trial = buildWarmup(library, Math.random, DEFINITIONS, warmup);
  const { folder, video } = trial.clip;
  slide.innerHTML = `<p class="eyebrow"></p><h1></h1><p class="lead"></p><div class="trial-stage"></div>`;
  slide.querySelector(".eyebrow")!.textContent = `Blind test · ${test.name.toLowerCase()} · practice warm-up`;
  slide.querySelector("h1")!.textContent = QUESTION;
  slide.querySelector(".lead")!.textContent =
    `${DEFINITION} This first one is easy to spot, and not scored.` + (test.warmup === true ? "" : ` ${WATCH_A_WHOLE_MOVE}`);
  const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
  const reveal = document.createElement("div");
  const bar = answerBar((answer) => {
    bar.disable(answer);
    const actions = document.createElement("div");
    actions.className = "actions";
    actions.innerHTML = `
      <button type="button" class="button ghost" data-action="again">Another warm-up</button>
      <button type="button" class="button" data-action="start">Start the test →</button>`;
    actions.querySelector('[data-action="again"]')!.addEventListener("click", () => {
      player.pause();
      practice(slide, library, test);
    });
    actions.querySelector('[data-action="start"]')!.addEventListener("click", () => {
      player.pause();
      start();
    });
    const card = revealCard(trial, answer, { ...player.health }, player);
    card.append(actions);
    reveal.replaceChildren(card);
  });
  slide.querySelector(".trial-stage")!.replaceChildren(player.element, bar.element, player.readout, reveal);
  player.play();
}

function question(
  slide: HTMLElement,
  library: ClipLibrary,
  test: TestDefinition,
  run: readonly Trial[],
  answers: AnsweredTrial[],
): void {
  const trial = run[answers.length];
  if (!trial) {
    void results(slide, library, test, answers);
    return;
  }
  const { folder, video } = trial.clip;
  slide.innerHTML = `<p class="eyebrow"></p><h1></h1><p class="lead"></p><div class="trial-stage"></div>`;
  slide.querySelector(".eyebrow")!.textContent =
    `Blind test · ${test.name.toLowerCase()} · question ${answers.length + 1} of ${run.length}${trial.definition.category === "warm-up" ? " · warm-up" : ""}`;
  slide.querySelector("h1")!.textContent = QUESTION;
  slide.querySelector(".lead")!.textContent = test.warmup ? DEFINITION : `${DEFINITION} ${WATCH_A_WHOLE_MOVE}`;
  const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
  let started = performance.now();
  player.video.addEventListener("playing", () => (started = performance.now()), { once: true });
  const bar = answerBar((answer) => {
    bar.disable(answer);
    const health = { ...player.health };
    player.pause();
    answers.push({ trial, answer, answerMs: performance.now() - started, health });
    setTimeout(() => question(slide, library, test, run, answers), 250);
  });
  slide.querySelector(".trial-stage")!.replaceChildren(player.element, bar.element, player.readout);
  player.play();
}

async function results(slide: HTMLElement, library: ClipLibrary, test: TestDefinition, answers: AnsweredTrial[]): Promise<void> {
  const record = buildRecord(
    answers,
    latestViewingReport(),
    await hashText(library.manifestText),
    new Date(),
    navigator.userAgent,
    test.id,
  );
  saveToHistory(record);
  const actions = renderResults(
    slide,
    record,
    `Blind test · ${test.name.toLowerCase()} · result`,
    answers.map(foldOut),
    preferenceTally(answers),
  );
  actions.innerHTML = `
    <a class="button" href="#/topics">Next: what you just saw, explained →</a>
    <a class="button ghost" href="#/menu">Menu</a>`;
  actions.append(...recordButtons(record));
  const again = Object.assign(document.createElement("button"), {
    type: "button",
    className: "button ghost",
    textContent: "Take a test again",
  });
  again.addEventListener("click", () => intro(slide, library));
  actions.append(again);
}

/** The saved results (oldest first), showing the one at `index` with older and newer buttons to step through them; `open`
 * shows another one (through the address, so the browser's Back works). */
export function showResultHistory(
  slide: HTMLElement,
  library: ClipLibrary,
  history: readonly ResultRecord[],
  index: number,
  back: () => void,
  open: (index: number) => void,
): void {
  const record = history[index];
  if (!record) return;
  slide.querySelectorAll("video").forEach((video) => video.pause());
  showSavedResult(slide, library, record, back);
  const nav = document.createElement("div");
  nav.className = "result-nav";
  const step = (to: number, text: string): HTMLButtonElement => {
    const button = Object.assign(document.createElement("button"), {
      type: "button",
      className: "button ghost",
      textContent: text,
      disabled: history[to] === undefined,
    });
    button.addEventListener("click", () => open(to));
    return button;
  };
  const position = Object.assign(document.createElement("span"), {
    className: "result-position",
    textContent: `Result ${index + 1} of ${history.length} · ${record.date}`,
  });
  const kept = Object.assign(document.createElement("span"), {
    className: "result-kept",
    textContent: "Kept in this browser only",
  });
  nav.append(step(index - 1, "‹ Older"), position, step(index + 1, "Newer ›"), kept);
  slide.prepend(nav);
}

/** A saved result, shown like one just taken (its questions can be watched again), with a way back. A result of an earlier test
 * version, whose clips are gone, lists its questions with their verdicts and what each box was, without the video. */
export function showSavedResult(slide: HTMLElement, library: ClipLibrary, record: ResultRecord, back: () => void): void {
  // Every question that still exists plays again; one changed in a later version of the test lists what each box was
  const answers = restoreEach(record, library);
  const eyebrow = `Previous result · ${record.date}`;
  const tally = tallyByMotion(
    record.trials
      .filter((saved) => isPreference(saved.category))
      .map((saved) => ({ motion: saved.motion, choice: chosen(saved.answer, saved.top, saved.bottom) })),
  );
  const rows = record.trials.map((saved, index) => {
    const answer = answers[index];
    return answer ? foldOut(answer) : savedRow(saved);
  });
  const actions = renderResults(slide, record, eyebrow, rows, tally);
  const gone = answers.filter((answer) => answer === null).length;
  const similar = answers.filter((answer) => answer?.similar).length;
  const notes = [
    similar > 0
      ? `${similar} of the questions changed in a later version of the test: they play today's version of their clip, with ` +
        "your answer as you gave it."
      : "",
    gone > 0
      ? gone === answers.length
        ? `From an earlier version of the test (version ${record.testVersion}): its clips are gone, so the questions cannot ` +
          "play again. Open a row to see what each box was."
        : `${gone} cannot play again: open one to see what each box was.`
      : "",
  ].filter(Boolean);
  if (notes.length > 0) slide.querySelector(".hint")!.textContent = notes.join(" ");
  const backButton = Object.assign(document.createElement("button"), {
    type: "button",
    className: "button",
    textContent: "← Back to the tests",
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

/** The results view: score, categories with the preference tally, viewing summary and the question rows; returns the (empty)
 * actions bar. */
function renderResults(
  slide: HTMLElement,
  record: ResultRecord,
  eyebrow: string,
  rows: readonly HTMLElement[],
  tally: readonly string[],
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
  // The categories of the result's test, or, for a result from before there was a choice, the ones it has
  const test = record.test === undefined ? null : testById(record.test);
  const shown = (
    ["warm-up", "pacing", "late-frames", "late-preference", "frame-rate", "identical", "preference"] as const
  ).filter((category) =>
    test
      ? category === "warm-up"
        ? test.warmup
        : test.categories.includes(category)
      : record.trials.some((saved) => saved.category === category),
  );
  const scoredNames = shown.filter((category) => !isPreference(category)).map((category) => CATEGORIES[category].name);
  slide.querySelector(".lead")!.textContent =
    `Scored: ${scoredNames.join(", ").toLowerCase()}.` +
    (shown.some(isPreference) ? " The preference questions have no right answer." : "");
  const categories = slide.querySelector(".categories")!;
  for (const category of shown) {
    const row = document.createElement("div");
    row.className = "category-row";
    const scored = byCategory[category];
    const value = scored ? `${scored.correct} of ${scored.of}` : "Not scored";
    row.innerHTML = `<span class="category-name"></span><span class="category-score"></span><span class="category-meaning"></span>`;
    row.querySelector(".category-name")!.textContent = CATEGORIES[category].name;
    row.querySelector(".category-score")!.textContent = value;
    row.querySelector(".category-meaning")!.textContent = CATEGORIES[category].meaning;
    if (isPreference(category)) {
      const list = document.createElement("ul");
      list.className = "tally";
      for (const line of tally) list.append(Object.assign(document.createElement("li"), { textContent: line }));
      row.querySelector(".category-meaning")!.append(list);
    }
    categories.append(row);
  }
  slide.querySelector(".setup")!.textContent = viewingSummary(record);
  slide.querySelector(".trial-list")!.append(...rows);
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

/** A result row's summary line: number, category and movement, and the verdict marked right, wrong or a choice. */
function rowSummary(
  position: number,
  category: Category,
  motion: string,
  verdictLine: string,
  correct: boolean | null,
): HTMLElement {
  const summary = document.createElement("summary");
  summary.innerHTML = `<span class="trial-number"></span><span class="trial-kind"></span><span class="trial-verdict"></span>`;
  summary.querySelector(".trial-number")!.textContent = String(position + 1);
  summary.querySelector(".trial-kind")!.textContent = `${CATEGORIES[category]?.name ?? category} · ${motion} movement`;
  const verdictElement = summary.querySelector<HTMLElement>(".trial-verdict")!;
  verdictElement.textContent = verdictLine;
  verdictElement.dataset.kind = correct === null ? "choice" : correct ? "correct" : "wrong";
  return summary;
}

/** A row of a saved result whose clips are gone: its verdict, folding out to what each box was. */
function savedRow(saved: TrialRecord): HTMLElement {
  const row = document.createElement("details");
  row.className = "trial-row";
  const choice = chosen(saved.answer, saved.top, saved.bottom);
  row.append(
    rowSummary(
      saved.position,
      saved.category,
      saved.motion,
      verdictText(saved.category, saved.answer, saved.correct, choice),
      saved.correct,
    ),
  );
  const text = document.createElement("p");
  text.className = "saved-boxes";
  text.textContent = `Top: ${choiceName(saved.top)} (${saved.top}). Bottom: ${choiceName(saved.bottom)} (${saved.bottom}).`;
  row.append(text);
  return row;
}

/** A result row that folds out to the trial's video, reveal and chart; the video only plays while the row is open. */
function foldOut({ trial, answer, health }: AnsweredTrial): HTMLElement {
  const row = document.createElement("details");
  row.className = "trial-row";
  row.append(
    rowSummary(trial.position, trial.definition.category, trial.motion, verdict(trial, answer), isCorrect(trial, answer)),
  );
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
