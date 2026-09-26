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
} from "./trials";

const mode = (name: string): ModeEntry => ({
  mode: name,
  rate: Number.parseInt(name, 10),
  timer: name.includes("naive") ? "naive" : "ideal",
  noise: null,
  noiseWindowMs: null,
  label: name,
  frames: { refresh: [], animationErrorMs: [], dtMs: [], sampleMs: [] },
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
  it("hold 5 trials with unique ids: 2 identical, 1 pacing, 1 frame rate, 1 preference", () => {
    const ids = DEFINITIONS.trials.map((trial) => trial.id);
    expect(new Set(ids).size).toBe(5);
    const count = (category: string): number => DEFINITIONS.trials.filter((trial) => trial.category === category).length;
    expect([count("identical"), count("pacing"), count("frame-rate"), count("preference")]).toEqual([2, 1, 1, 1]);
  });

  it("never show 20 fps; ask every trial at the normal and the fast movement, the preference also at the slow one", () => {
    expect(DEFINITIONS.trials.filter((trial) => [trial.a, trial.b].some((mode) => mode.startsWith("20")))).toEqual([]);
    expect(DEFINITIONS.motions).toEqual(["normal", "fast"]);
    for (const trial of DEFINITIONS.trials)
      expect(trial.motions ?? DEFINITIONS.motions).toEqual(
        trial.category === "preference" ? ["normal", "fast", "slow"] : ["normal", "fast"],
      );
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
    expect(pairs.get("normal")).toHaveLength(2 + 3 * 2);
    // At fast also the warm-up pair (perfect 60 against the ±5 ms timer), its own
    expect(pairs.get("fast")).toHaveLength(2 + 3 * 2 + 2);
    // Slow: only the preference pair, both ways round
    expect(pairs.get("slow")).toEqual([
      ["30", "60-naive-4ms"],
      ["60-naive-4ms", "30"],
    ]);
  });
});

describe("a run", () => {
  it("starts with the warm-up, then every pair in each of its movements and both top/bottom orders", () => {
    const run = buildRun(library(), seededRandom(1));
    expect(run).toHaveLength(19);
    expect(run[0]?.definition.category).toBe("warm-up");
    expect(run[0]?.motion).toBe("fast");
    const ids = run.slice(1).map((trial) => trial.id);
    expect(new Set(ids).size).toBe(18);
    for (const trial of DEFINITIONS.trials) {
      for (const motion of trial.motions ?? DEFINITIONS.motions) {
        if (trial.a === trial.b) expect(ids).toContain(`${trial.id}-${motion}`);
        else for (const top of [trial.a, trial.b]) expect(ids).toContain(`${trial.id}-${motion}-top-${top}`);
      }
    }
    expect(run.map((trial) => trial.position)).toEqual([...Array(19).keys()]);
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
    expect(new Set(run.map((trial) => trial.motion))).toEqual(new Set(["normal", "fast", "slow"]));
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
    expect(result.overall).toEqual({ correct: 13, of: 13 });
    expect(result.byCategory).toEqual({
      "warm-up": { correct: 1, of: 1 },
      pacing: { correct: 4, of: 4 },
      "frame-rate": { correct: 4, of: 4 },
      identical: { correct: 4, of: 4 },
    });
    expect(score(run.map((trial) => ({ trial, answer: "same" as Answer }))).overall).toEqual({ correct: 4, of: 13 });
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
    expect(fetched.sort()).toEqual([
      "videos/box/fast/manifest.json",
      "videos/box/normal/manifest.json",
      "videos/box/slow/manifest.json",
    ]);
  });
});
