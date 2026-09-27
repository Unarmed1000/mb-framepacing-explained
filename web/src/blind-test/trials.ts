// The blind test's questions (trials.json), the clips that show them, a randomised run, and its scoring.

import definitions from "./trials.json";
import { loadManifestText, type VideoEntry } from "../manifest";

export type Answer = "top" | "bottom" | "same";
export type Category = "warm-up" | "pacing" | "late-frames" | "frame-rate" | "preference" | "late-preference" | "identical";

/** The categories with no right answer: a choice between two different weaknesses. */
export const isPreference = (category: Category): boolean => category === "preference" || category === "late-preference";

export interface TrialDefinition {
  id: string;
  category: Category;
  /** The two modes of the pair (video tool mode names); a run asks it once with each on top. */
  a: string;
  b: string;
  /** The smoother mode, "same" when both are the same clip, or null for a preference (no right answer). */
  smoother: string | null;
  /** The movements this trial uses (default: the test's), e.g. slow: the normal timing on a shorter path. */
  motions?: string[];
  /** Asked once per movement, with a random one of its modes on top, instead of once with each. */
  once?: boolean;
}

/** A warm-up: an easy pair, in its movements, and which mode is smoother. */
export interface Warmup {
  motions: string[];
  pairs: [string, string][];
  smoother: string;
}

/** One of the blind tests a visitor can choose: its trials by category, and its warm-up: true for the test-wide one, a warm-up
 * of its own, or false for none. */
export interface TestDefinition {
  id: string;
  name: string;
  warmup: boolean | Warmup;
  categories: Category[];
}

export interface Definitions {
  testVersion: number;
  tests: TestDefinition[];
  clip: { width: number; height: number; arguments: string[] };
  motions: string[];
  warmup: Warmup;
  trials: TrialDefinition[];
}

export const DEFINITIONS = definitions as Definitions;

/** The warm-up a test starts with, or null for none; without a test, the test-wide one. */
export function warmupOf(test?: TestDefinition, definitions: Definitions = DEFINITIONS): Warmup | null {
  if (test === undefined || test.warmup === true) return definitions.warmup;
  return test.warmup === false ? null : test.warmup;
}

/** Every warm-up: the test-wide one and the tests' own. */
export function allWarmups(definitions: Definitions = DEFINITIONS): Warmup[] {
  return [definitions.warmup, ...definitions.tests.flatMap((test) => (typeof test.warmup === "object" ? [test.warmup] : []))];
}

/** The test with this id; a missing one is an error. */
export function testById(id: string, definitions: Definitions = DEFINITIONS): TestDefinition {
  const test = definitions.tests.find((each) => each.id === id);
  if (!test) throw new Error(`no blind test named ${id}`);
  return test;
}

/** A clip of the test: its folder (relative to the page) and its manifest entry. */
export interface Clip {
  folder: string;
  video: VideoEntry;
}

/** One question of a run: what is asked, in which movement, and which clip shows it. */
export interface Trial {
  definition: TrialDefinition;
  /** The question's id: the trial's id, its movement and, for two different modes, the top one, e.g. "pacing-60-fast-top-60". */
  id: string;
  /** 0 for the warm-up, then 1, 2, ... */
  position: number;
  motion: string;
  clip: Clip;
}

/** The folder of a motion's clips, relative to the page (the single box, never the rows). */
export const folderFor = (motion: string): string => `videos/box/${motion}`;

/** Every clip of the test, keyed by motion, top mode and bottom mode. */
export class ClipLibrary {
  private readonly clips = new Map<string, Clip>();
  /** The manifests' text, in load order: what the clips hash of a result is made from. */
  manifestText = "";

  add(folder: string, motion: string, videos: readonly VideoEntry[]): void {
    for (const video of videos) {
      if (video.scene !== "box") continue;
      this.clips.set(ClipLibrary.key(motion, video.top.mode, video.bottom.mode), { folder, video });
    }
  }

  find(motion: string, top: string, bottom: string): Clip | undefined {
    return this.clips.get(ClipLibrary.key(motion, top, bottom));
  }

  private static key(motion: string, top: string, bottom: string): string {
    return `${motion}|${top}|${bottom}`;
  }
}

export async function loadClips(definitions: Definitions = DEFINITIONS): Promise<ClipLibrary> {
  const library = new ClipLibrary();
  const motions = [
    ...new Set([
      ...definitions.motions,
      ...definitions.trials.flatMap((trial) => trial.motions ?? []),
      ...definitions.warmup.motions,
    ]),
  ];
  for (const motion of motions) {
    const folder = folderFor(motion);
    const { manifest, text } = await loadManifestText(folder);
    library.add(folder, motion, manifest.videos);
    library.manifestText += text;
  }
  return library;
}

/** A small seeded random generator (mulberry32), so a run can be reproduced in tests. */
export function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

const pick = <T>(items: readonly T[], random: () => number): T => items[Math.floor(random() * items.length)]!;

function shuffled<T>(items: readonly T[], random: () => number): T[] {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index--) {
    const other = Math.floor(random() * (index + 1));
    [copy[index], copy[other]] = [copy[other]!, copy[index]!];
  }
  return copy;
}

/** Place a pair with the given mode on top, and look its clip up; a missing clip is an error. The id names the movement and,
 * when the two modes differ, which one is on top (e.g. "pacing-60-fast-top-60"). */
function placed(definition: TrialDefinition, position: number, motion: string, top: string, library: ClipLibrary): Trial {
  const bottom = top === definition.a ? definition.b : definition.a;
  const clip = library.find(motion, top, bottom);
  if (!clip) throw new Error(`no clip for ${definition.id}: ${motion}, top ${top}, bottom ${bottom}`);
  const id =
    definition.category === "warm-up"
      ? definition.id
      : definition.a === definition.b
        ? `${definition.id}-${motion}`
        : `${definition.id}-${motion}-top-${top}`;
  return { definition, id, position, motion, clip };
}

/** The warm-up trial alone: a random pair, motion and top/bottom of `warmup` (for the practice slide and a run's first
 * question). */
export function buildWarmup(
  library: ClipLibrary,
  random: () => number,
  definitions: Definitions = DEFINITIONS,
  warmup: Warmup = definitions.warmup,
): Trial {
  const [a, b] = pick(warmup.pairs, random);
  const trial: TrialDefinition = { id: "warm-up", category: "warm-up", a, b, smoother: warmup.smoother };
  return placed(trial, 0, pick(warmup.motions, random), random() < 0.5 ? a : b, library);
}

/** A question after the warm-up: a trial, its movement, and which of its modes is on top. */
export interface Question {
  definition: TrialDefinition;
  motion: string;
  /** The mode on top, or null for a trial asked once: the run picks one at random. */
  top: string | null;
}

/** Every question after the warm-up: each trial in each of its movements (normal and fast; the preference also slow) and, when its two
 * modes differ, with each of them on top once, or, for a trial asked once, one of them; with a `test`, only its trials. */
export function questions(definitions: Definitions = DEFINITIONS, test?: TestDefinition): Question[] {
  const tops = (definition: TrialDefinition): (string | null)[] =>
    definition.a === definition.b ? [definition.a] : definition.once ? [null] : [definition.a, definition.b];
  const trials = test ? definitions.trials.filter((trial) => test.categories.includes(trial.category)) : definitions.trials;
  return trials.flatMap((definition) =>
    (definition.motions ?? definitions.motions).flatMap((motion) => tops(definition).map((top) => ({ definition, motion, top }))),
  );
}

/** A run: the warm-up first (unless the `test` has none), then every question once, in random order; with a `test`, only its
 * questions. */
export function buildRun(
  library: ClipLibrary,
  random: () => number,
  definitions: Definitions = DEFINITIONS,
  test?: TestDefinition,
): Trial[] {
  const warmup = warmupOf(test, definitions);
  const run = warmup ? [buildWarmup(library, random, definitions, warmup)] : [];
  shuffled(questions(definitions, test), random).forEach(({ definition, motion, top }, index) => {
    const chosen = top ?? (random() < 0.5 ? definition.a : definition.b);
    run.push(placed(definition, index + 1, motion, chosen, library));
  });
  return run;
}

/** The right answer of a trial as placed, or null for a preference. */
export function expectedAnswer(trial: Trial): Answer | null {
  const { smoother } = trial.definition;
  if (smoother === null) return null;
  if (smoother === "same") return "same";
  return trial.clip.video.top.mode === smoother ? "top" : "bottom";
}

/** Whether an answer is right, or null for a preference. */
export function isCorrect(trial: Trial, answer: Answer): boolean | null {
  const expected = expectedAnswer(trial);
  return expected === null ? null : answer === expected;
}

export interface CategoryScore {
  correct: number;
  of: number;
}

/** The score per scored category and overall; preferences are not scored. */
export function score(answers: readonly { trial: Trial; answer: Answer }[]): {
  overall: CategoryScore;
  byCategory: Partial<Record<Category, CategoryScore>>;
} {
  const byCategory: Partial<Record<Category, CategoryScore>> = {};
  const overall: CategoryScore = { correct: 0, of: 0 };
  for (const { trial, answer } of answers) {
    const correct = isCorrect(trial, answer);
    if (correct === null) continue;
    const category = (byCategory[trial.definition.category] ??= { correct: 0, of: 0 });
    category.of += 1;
    overall.of += 1;
    if (correct) {
      category.correct += 1;
      overall.correct += 1;
    }
  }
  return { overall, byCategory };
}

/** Every top/bottom pair the test needs per motion (identical pairs once, the others in both orders): for the clip export. */
export function requiredPairs(definitions: Definitions = DEFINITIONS): Map<string, [string, string][]> {
  const pairs = new Map<string, Set<string>>();
  const add = (motion: string, a: string, b: string): void => {
    const set = pairs.get(motion) ?? new Set<string>();
    set.add(`${a}:${b}`);
    set.add(`${b}:${a}`);
    pairs.set(motion, set);
  };
  for (const trial of definitions.trials)
    for (const motion of trial.motions ?? definitions.motions) add(motion, trial.a, trial.b);
  for (const warmup of allWarmups(definitions))
    for (const motion of warmup.motions) for (const [a, b] of warmup.pairs) add(motion, a, b);
  return new Map([...pairs].map(([motion, set]) => [motion, [...set].map((pair) => pair.split(":") as [string, string])]));
}
