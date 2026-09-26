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
  it("hold 9 trials with unique ids: 3 identical, 1 pacing, 3 frame rate, 2 preferences", () => {
    const ids = DEFINITIONS.trials.map((trial) => trial.id);
    expect(new Set(ids).size).toBe(9);
    const count = (category: string): number => DEFINITIONS.trials.filter((trial) => trial.category === category).length;
    expect([count("identical"), count("pacing"), count("frame-rate"), count("preference")]).toEqual([3, 1, 3, 2]);
  });

  it("show 20 Hz only with the slow movement (a shorter path), and everything else never slow", () => {
    const runs = [1, 2, 3, 4, 5, 6, 7, 8].map((seed) => buildRun(library(), seededRandom(seed)));
    const twenty = runs.flat().filter((trial) => [trial.definition.a, trial.definition.b].includes("20"));
    expect(twenty.length).toBeGreaterThan(0);
    expect(new Set(twenty.map((trial) => trial.motion))).toEqual(new Set(["slow"]));
    for (const motion of ["normal", "fast"])
      expect(
        requiredPairs()
          .get(motion)
          ?.some((pair) => pair.includes("20")),
      ).toBe(false);
    expect(
      requiredPairs()
        .get("slow")
        ?.every((pair) => pair.includes("20")),
    ).toBe(true);
  });

  it("pair the perfect 20 with every perfect, itself included", () => {
    const withTwenty = DEFINITIONS.trials
      .filter((trial) => [trial.a, trial.b].includes("20"))
      .map((trial) => [trial.a, trial.b].sort().join(":"));
    for (const other of ["20", "30", "60"]) expect(withTwenty).toContain(["20", other].sort().join(":"));
  });

  it("use the bad 30 only against the perfect 20, at the slow movement only, as the ±4 ms extreme", () => {
    const withBad30 = DEFINITIONS.trials.filter((trial) => [trial.a, trial.b].some((mode) => mode.startsWith("30-naive")));
    expect(withBad30.map((trial) => [trial.a, trial.b].sort().join(":"))).toEqual(["20:30-naive-4ms"]);
    expect(withBad30[0]?.motions).toEqual(["slow"]);
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
    expect(pairs.get("fast")).toHaveLength(2 + 3 * 2 + 2);
    expect(pairs.get("slow")).toHaveLength(1 + 3 * 2);
  });
});

describe("a run", () => {
  it("starts with the warm-up, then every pair in each of its movements and both top/bottom orders", () => {
    const run = buildRun(library(), seededRandom(1));
    expect(run).toHaveLength(24);
    expect(run[0]?.definition.category).toBe("warm-up");
    expect(run[0]?.motion).toBe("fast");
    const ids = run.slice(1).map((trial) => trial.id);
    expect(new Set(ids).size).toBe(23);
    for (const trial of DEFINITIONS.trials) {
      for (const motion of trial.motions ?? DEFINITIONS.motions) {
        if (trial.a === trial.b) expect(ids).toContain(`${trial.id}-${motion}`);
        else for (const top of [trial.a, trial.b]) expect(ids).toContain(`${trial.id}-${motion}-top-${top}`);
      }
    }
    expect(ids.some((id) => id.startsWith("pref-20-vs-bad-30-fast"))).toBe(false);
    expect(run.map((trial) => trial.position)).toEqual([...Array(24).keys()]);
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
    expect(new Set(pacingFast.map((trial) => trial.clip.video.top.mode))).toEqual(new Set(["60", "60-naive-heavy"]));
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
    expect(expectedAnswer(byId("pref-20-vs-bad-30"))).toBeNull();
    expect(isCorrect(byId("pref-20-vs-bad-30"), "top")).toBeNull();
  });

  it("counts scored categories only", () => {
    const answers = run.map((trial) => ({ trial, answer: (expectedAnswer(trial) ?? "top") as Answer }));
    const result = score(answers);
    expect(result.overall).toEqual({ correct: 18, of: 18 });
    expect(result.byCategory).toEqual({
      "warm-up": { correct: 1, of: 1 },
      pacing: { correct: 4, of: 4 },
      "frame-rate": { correct: 8, of: 8 },
      identical: { correct: 5, of: 5 },
    });
    expect(score(run.map((trial) => ({ trial, answer: "same" as Answer }))).overall).toEqual({ correct: 5, of: 18 });
  });
});

describe("loading the clips", () => {
  it("fetches the manifest of every movement a trial or the warm-up uses, the slow one included", async () => {
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
