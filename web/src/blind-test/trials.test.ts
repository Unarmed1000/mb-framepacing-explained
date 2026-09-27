import { describe, expect, it, vi } from "vitest";

import type { ModeEntry, VideoEntry } from "../manifest";
import {
  buildRun,
  ClipLibrary,
  DEFINITIONS,
  loadClips,
  expectedAnswer,
  isCorrect,
  requiredPairs,
  score,
  seededRandom,
  type Answer,
  type Trial,
  testById,
  warmupOf,
} from "./trials";

const mode = (name: string): ModeEntry => ({
  mode: name,
  rate: Number.parseInt(name, 10),
  timer: name.includes("naive") ? "naive" : "ideal",
  noise: null,
  noiseWindowMs: null,
  label: name,
  frames: { refresh: [], animationErrorMs: [], dtMs: [], sampleMs: [], late: [] },
});

/** A library holding exactly the clips the definitions require. */
function library(): ClipLibrary {
  const clips = new ClipLibrary();
  for (const [motion, pairs] of requiredPairs()) {
    const videos: VideoEntry[] = pairs.map(([top, bottom]) => ({
      file: `${motion}_top-${top}_bottom-${bottom}.mp4`,
      speed: motion,
      scene: "box",
      fps: 60,
      frameCount: 480,
      videoFrameCount: 480,
      width: 1280,
      height: 384,
      top: mode(top),
      bottom: mode(bottom),
    }));
    clips.add(`videos/box/${motion}`, motion, videos);
  }
  return clips;
}

describe("the trial definitions", () => {
  it("hold 9 trials: 2 identical, 1 pacing, 2 late frames, 1 frame rate, 1 preference, 2 late frames preferences", () => {
    // 60 with late frames against 20 has a clip of its own at each movement (three groups of late frames in every move: 2 s at
    // normal, 1 s at fast), so two definitions with one id
    const ids = DEFINITIONS.trials.map((trial) => trial.id);
    expect(new Set(ids).size).toBe(9);
    expect(ids.filter((id) => id === "late-vs-20")).toHaveLength(2);
    const count = (category: string): number => DEFINITIONS.trials.filter((trial) => trial.category === category).length;
    expect([
      count("identical"),
      count("pacing"),
      count("late-frames"),
      count("frame-rate"),
      count("preference"),
      count("late-preference"),
    ]).toEqual([2, 1, 2, 1, 1, 3]);
  });

  it("never show 20 fps in the jitter test; ask every trial at the normal and the fast movement, adapting the rate at the fast one only", () => {
    // No 20 fps in the jitter test; the late frames test compares a 60 with late frames against an even 20
    const jitter = testById("jitter");
    const inJitter = DEFINITIONS.trials.filter((trial) => jitter.categories.includes(trial.category));
    expect(inJitter.filter((trial) => [trial.a, trial.b].some((mode) => mode.startsWith("20")))).toEqual([]);
    expect(DEFINITIONS.motions).toEqual(["normal", "fast"]);
    const motions = new Map<string, string[]>();
    for (const trial of DEFINITIONS.trials)
      motions.set(trial.id, [...(motions.get(trial.id) ?? []), ...(trial.motions ?? DEFINITIONS.motions)]);
    for (const [id, each] of motions) expect(each).toEqual(id === "adapt-busy" ? ["fast"] : ["normal", "fast"]);
    expect(DEFINITIONS.trials.filter((trial) => trial.once)).toEqual([]);
  });

  it("never compare two bad timers", () => {
    const bad = (mode: string): boolean => mode.includes("naive");
    expect(DEFINITIONS.trials.filter((trial) => bad(trial.a) && bad(trial.b))).toEqual([]);
  });

  it("never use the rows, and the warm-up is a perfect 60 at fast speed", () => {
    expect([...DEFINITIONS.motions, ...DEFINITIONS.warmup.motions].every((motion) => !motion.startsWith("ui"))).toBe(true);
    expect(DEFINITIONS.warmup).toMatchObject({ motions: ["fast"], smoother: "60" });
    expect(DEFINITIONS.warmup.pairs.every((pair) => pair.includes("60"))).toBe(true);
  });

  it("need identical pairs once and the other pairs in both orders, per motion", () => {
    const pairs = requiredPairs();
    expect(pairs.get("normal")).toHaveLength(2 + 6 * 2);
    // At fast also adapting the rate and the two warm-up pairs (perfect 60 against the ±5 ms timer, and against back-to-back
    // late frames), their own
    expect(pairs.get("fast")).toHaveLength(2 + 7 * 2 + 2 + 2);
    // Never the slow movement (the short path near the centre)
    expect([...pairs.keys()].sort()).toEqual(["fast", "normal"]);
  });
});

describe("a run", () => {
  it("starts with the warm-up, then every pair in each of its movements and both top/bottom orders (one for a trial asked once)", () => {
    const run = buildRun(library(), seededRandom(1));
    expect(run).toHaveLength(31);
    expect(run[0]?.definition.category).toBe("warm-up");
    expect(run[0]?.motion).toBe("fast");
    const ids = run.slice(1).map((trial) => trial.id);
    expect(new Set(ids).size).toBe(30);
    for (const trial of DEFINITIONS.trials) {
      for (const motion of trial.motions ?? DEFINITIONS.motions) {
        if (trial.a === trial.b) expect(ids).toContain(`${trial.id}-${motion}`);
        else if (trial.once) expect(ids.filter((id) => id.startsWith(`${trial.id}-${motion}-top-`))).toHaveLength(1);
        else for (const top of [trial.a, trial.b]) expect(ids).toContain(`${trial.id}-${motion}-top-${top}`);
      }
    }
    expect(run.map((trial) => trial.position)).toEqual([...Array(31).keys()]);
  });

  it("puts the questions in a different random order from run to run", () => {
    const orders = new Set(
      [1, 2, 3, 4, 5].map((seed) =>
        buildRun(library(), seededRandom(seed))
          .map((trial) => trial.id)
          .join(),
      ),
    );
    expect(orders.size).toBeGreaterThan(1);
  });

  it("shows each pair with each of its modes on top, in one run", () => {
    const run = buildRun(library(), seededRandom(3));
    const pacingFast = run.filter((trial) => trial.definition.id === "pacing-60" && trial.motion === "fast");
    expect(new Set(pacingFast.map((trial) => trial.clip.video.top.mode))).toEqual(new Set(["60", "60-naive-4ms"]));
    expect(new Set(run.map((trial) => trial.motion))).toEqual(new Set(["normal", "fast"]));
  });
});

describe("scoring", () => {
  const run = buildRun(library(), seededRandom(7));
  const byId = (id: string): Trial => run.find((trial) => trial.definition.id === id)!;

  it("expects the smoother mode's side, 'same' for identical clips, and nothing for preferences", () => {
    const pacing = byId("pacing-60");
    expect(expectedAnswer(pacing)).toBe(pacing.clip.video.top.mode === "60" ? "top" : "bottom");
    expect(expectedAnswer(byId("same-30"))).toBe("same");
    expect(expectedAnswer(byId("pref-30-vs-bad-60"))).toBeNull();
    expect(isCorrect(byId("pref-30-vs-bad-60"), "top")).toBeNull();
  });

  it("counts scored categories only", () => {
    const answers = run.map((trial) => ({ trial, answer: (expectedAnswer(trial) ?? "top") as Answer }));
    const result = score(answers);
    expect(result.overall).toEqual({ correct: 19, of: 19 });
    expect(result.byCategory).toEqual({
      "warm-up": { correct: 1, of: 1 },
      pacing: { correct: 4, of: 4 },
      // Slow frames at two speeds and adapting the rate at one, both ways round
      "late-frames": { correct: 6, of: 6 },
      "frame-rate": { correct: 4, of: 4 },
      identical: { correct: 4, of: 4 },
    });
    expect(score(run.map((trial) => ({ trial, answer: "same" as Answer }))).overall).toEqual({ correct: 4, of: 19 });
  });
});

describe("the two tests", () => {
  it("split the trials: every category in exactly one test, the warm-up only in the jitter one", () => {
    const categories = DEFINITIONS.tests.flatMap((test) => test.categories);
    expect(new Set(categories).size).toBe(categories.length);
    expect(new Set(categories)).toEqual(new Set(DEFINITIONS.trials.map((trial) => trial.category)));
    // Each its own warm-up: the jitter test the test-wide one, late frames a perfect 60 against back-to-back late frames
    expect(DEFINITIONS.tests.map((test) => [test.id, warmupOf(test)?.pairs])).toEqual([
      ["jitter", DEFINITIONS.warmup.pairs],
      ["late-frames", [["60", "60-diagram-slow-frames"]]],
    ]);
  });

  it("run only their own questions after their own warm-up: jitter 18, late frames 14", () => {
    const jitter = buildRun(library(), seededRandom(2), DEFINITIONS, testById("jitter"));
    expect(jitter).toHaveLength(17);
    expect(jitter[0]?.definition.category).toBe("warm-up");
    expect(jitter.some((trial) => trial.definition.category === "late-frames")).toBe(false);
    const late = buildRun(library(), seededRandom(2), DEFINITIONS, testById("late-frames"));
    expect(late).toHaveLength(15);
    expect(late[0]?.clip.video.bottom.mode === "60" ? late[0].clip.video.top.mode : late[0]?.clip.video.bottom.mode).toBe(
      "60-diagram-slow-frames",
    );
    expect(late.slice(1).every((trial) => ["late-frames", "late-preference"].includes(trial.definition.category))).toBe(true);
  });
});

describe("loading the clips", () => {
  it("fetches the manifest of every movement a trial or the warm-up uses", async () => {
    const fetched: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      fetched.push(url);
      return Promise.resolve(new Response(JSON.stringify({ settings: {}, videos: [] })));
    });
    try {
      await loadClips();
    } finally {
      vi.unstubAllGlobals();
    }
    expect(fetched.sort()).toEqual(["videos/box/fast/manifest.json", "videos/box/normal/manifest.json"]);
  });
});
