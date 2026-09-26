// The answer buttons and the reveal of a trial (verdict, what each box was, the animation error chart), shared by the warm-up
// practice and the results list.

import { errorChart } from "../charts/error-chart";
import type { ModeEntry } from "../manifest";
import type { PixelVideo, PlaybackHealth } from "../video/pixel-video";
import { expectedAnswer, isCorrect, type Answer, type Trial } from "./trials";

/** A box's mode in a few words, for the preference answers: "perfect 30 fps", "jittery 60 fps". */
export function choiceName(mode: ModeEntry): string {
  return `${mode.timer === "ideal" ? "perfect" : "jittery"} ${mode.rate} fps`;
}

/** What a preference answer chose: the chosen box's mode in a few words, or "no difference". */
export function preferenceChoice(trial: Trial, answer: Answer): string {
  if (answer === "same") return "no difference";
  return choiceName(answer === "top" ? trial.clip.video.top : trial.clip.video.bottom);
}

/** The movements from slowest to fastest, for ordering per-movement summaries. */
const MOTION_ORDER = ["slow", "normal", "fast"];

/** The preference answers counted by choice, per movement from slow to fast (the answer can change with the speed: faster motion
 * may favour the higher frame rate), one line each: "Slow: perfect 30 fps ×2", "Normal: perfect 30 fps ×1, jittery 60 fps ×1", ...
 * Empty when there were none. */
export function preferenceTally(answers: readonly { trial: Trial; answer: Answer }[]): string[] {
  const byMotion = new Map<string, Map<string, number>>();
  for (const { trial, answer } of answers) {
    if (trial.definition.category !== "preference") continue;
    const counts = byMotion.get(trial.motion) ?? new Map<string, number>();
    const choice = preferenceChoice(trial, answer);
    counts.set(choice, (counts.get(choice) ?? 0) + 1);
    byMotion.set(trial.motion, counts);
  }
  const rank = (motion: string): number => {
    const index = MOTION_ORDER.indexOf(motion);
    return index < 0 ? MOTION_ORDER.length : index;
  };
  return [...byMotion]
    .sort(([x], [y]) => rank(x) - rank(y))
    .map(([motion, counts]) => {
      const choices = [...counts].map(([name, count]) => `${name} ×${count}`).join(", ");
      return `${motion.charAt(0).toUpperCase()}${motion.slice(1)}: ${choices}`;
    });
}

/** The one-word-ish verdict of an answer. */
export function verdict(trial: Trial, answer: Answer): string {
  const correct = isCorrect(trial, answer);
  if (correct === null) return answer === "same" ? "You saw no difference" : `You chose the ${preferenceChoice(trial, answer)}`;
  if (correct) return "Correct";
  const expected = expectedAnswer(trial);
  if (expected === "same") return "They were the same";
  if (answer === "same") return "There was a difference";
  return "Not this time";
}

/** What the trial showed, in plain words. */
export function explanation(trial: Trial): string {
  const { top, bottom } = trial.clip.video;
  const { category, smoother } = trial.definition;
  const which = `Top: ${top.label}. Bottom: ${bottom.label}.`;
  switch (category) {
    case "identical":
      return `Both halves were the same clip (${top.label}). Most people see a difference that is not there.`;
    case "preference":
      return `${which} There is no right answer here: each has a different weakness, and your choice shows which one you notice more.`;
    case "frame-rate":
      return top.timer === "ideal" && bottom.timer === "ideal"
        ? `${which} Both were evenly paced; the 60 shows twice as many frames, so its motion is smoother. A lower frame rate is not stutter, but it is less smooth.`
        : `${which} The 60 was perfect; the 30 was both a lower frame rate and unevenly timed.`;
    default: {
      const [perfect, other] = smoother === top.mode ? ["top", bottom] : ["bottom", top];
      return (
        `The ${perfect} box was smoother: it had the perfect timer. The other one stuttered (${other.label}): its timer reads the ` +
        "clock a little early or late on many frames, so those frames show a slightly wrong moment. Both boxes' frames reach the " +
        "screen perfectly on time: only the animation error below shows the difference."
      );
    }
  }
}

/** The playback line: what the browser's frame timing said about the clip while it was watched. */
export function playbackLine(health: PlaybackHealth): string {
  const { presented, dropped, late, early } = health;
  const off = dropped + late + early;
  if (off === 0) return "Playback looked clean: the browser's frame timing put every video frame on the 60 fps rhythm.";
  const share = presented > 0 ? Math.round((off / presented) * 1000) / 10 : 0;
  return (
    `The browser's frame timing (its own estimate, not a measurement of the screen) put ${off} of ${presented} video frames ` +
    `off the 60 fps rhythm (${share} %: ${dropped} dropped, ${late} late, ${early} early). A few can be estimation noise; many ` +
    "mean the playback itself was uneven, so check the viewing setup and try again."
  );
}

/** A card revealing a trial: verdict, explanation, playback line and the chart, its playhead following `player`. */
export function revealCard(trial: Trial, answer: Answer, health: PlaybackHealth, player: PixelVideo): HTMLElement {
  const correct = isCorrect(trial, answer);
  const { video } = trial.clip;
  const chart = errorChart(
    [
      { title: "Top", mode: video.top },
      { title: "Bottom", mode: video.bottom },
    ],
    video.frameCount,
    video.fps,
  );
  player.onFrame = (mediaTime) => chart.setTime(mediaTime);
  const card = document.createElement("div");
  card.className = "card result";
  card.dataset.correct = correct === null ? "none" : String(correct);
  card.innerHTML = `<h2></h2><p class="lead"></p><p class="health"></p><div class="chart-holder"></div>`;
  card.querySelector("h2")!.textContent = verdict(trial, answer);
  card.querySelector(".lead")!.textContent = explanation(trial);
  card.querySelector(".health")!.textContent = playbackLine(health);
  card.querySelector(".chart-holder")!.append(chart.svg);
  return card;
}

/** The three answer buttons (and T / B / N keys while the bar is on screen). */
export function answerBar(onAnswer: (answer: Answer) => void): { element: HTMLElement; disable(chosen: Answer): void } {
  const element = document.createElement("div");
  element.className = "answers";
  element.innerHTML = `
    <button type="button" class="button answer" data-answer="top">Top is smoother <kbd>T</kbd></button>
    <button type="button" class="button answer" data-answer="bottom">Bottom is smoother <kbd>B</kbd></button>
    <button type="button" class="button answer" data-answer="same">No difference <kbd>N</kbd></button>`;
  let done = false;
  const choose = (answer: Answer): void => {
    if (done) return;
    done = true;
    document.removeEventListener("keydown", keys);
    onAnswer(answer);
  };
  const keys = (event: KeyboardEvent): void => {
    if (!element.isConnected || element.closest("[hidden]") || event.ctrlKey || event.altKey || event.metaKey) return;
    const answer = ({ t: "top", b: "bottom", n: "same" } as const)[event.key.toLowerCase() as "t" | "b" | "n"];
    if (answer) choose(answer);
  };
  document.addEventListener("keydown", keys);
  element.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-answer]");
    if (button && !button.disabled) choose(button.dataset.answer as Answer);
  });
  return {
    element,
    disable(chosen: Answer) {
      element.querySelectorAll("button").forEach((button) => (button.disabled = true));
      element.querySelector(`[data-answer="${chosen}"]`)?.classList.add("chosen");
    },
  };
}

/** The question heading and definition, the same for every trial. */
export const QUESTION = "Which box has the smoother movement?";
export const DEFINITION =
  "Smooth: the box glides evenly, without small jumps where it speeds up or slows down (stutter). Both can stutter, or neither; " +
  "if you see no difference, say so.";
