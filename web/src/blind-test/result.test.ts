import { describe, expect, it } from "vitest";

import type { ModeEntry, VideoEntry } from "../manifest";
import { browserFamily, buildRecord, RESULT_FORMAT, type AnsweredTrial } from "./result";
import { preferenceTally, verdict } from "./reveal";
import { DEFINITIONS, type Trial, type TrialDefinition } from "./trials";

const mode = (name: string): ModeEntry => ({
  mode: name,
  rate: Number.parseInt(name, 10),
  timer: name.includes("naive") ? "naive" : "ideal",
  noise: null,
  noiseWindowMs: null,
  label: name,
  frames: { refresh: [], animationErrorMs: [], dtMs: [], sampleMs: [] },
});

function trial(id: string, top: string, bottom: string, position = 1): Trial {
  const definition = DEFINITIONS.trials.find((item) => item.id === id) as TrialDefinition;
  const video: VideoEntry = {
    file: "clip.mp4",
    speed: "fast",
    scene: "box",
    fps: 60,
    frameCount: 480,
    videoFrameCount: 480,
    width: 1280,
    height: 384,
    top: mode(top),
    bottom: mode(bottom),
  };
  return { definition, id: `${id}-fast`, position, motion: "fast", clip: { folder: "videos/box/fast", video } };
}

const health = { presented: 480, dropped: 0, late: 2, early: 1 };

describe("verdict", () => {
  it("names each kind of answer", () => {
    expect(verdict(trial("pacing-60", "60", "60-naive-heavy"), "top")).toBe("Correct");
    expect(verdict(trial("pacing-60", "60", "60-naive-heavy"), "bottom")).toBe("Not this time");
    expect(verdict(trial("pacing-60", "60", "60-naive-heavy"), "same")).toBe("There was a difference");
    expect(verdict(trial("same-60", "60", "60"), "top")).toBe("They were the same");
    expect(verdict(trial("same-60", "60", "60"), "same")).toBe("Correct");
    expect(verdict(trial("pref-30-vs-bad-60", "30", "60-naive-4ms"), "bottom")).toBe("You chose the jittery 60 fps");
    expect(verdict(trial("pref-30-vs-bad-60", "60-naive-4ms", "30"), "bottom")).toBe("You chose the perfect 30 fps");
    expect(verdict(trial("pref-30-vs-bad-60", "30", "60-naive-4ms"), "same")).toBe("You saw no difference");
  });
});

describe("the preference tally", () => {
  it("counts each choice by name, whichever box it was in, per movement from slow to fast", () => {
    const at = (motion: string, top: string, bottom: string): Trial => ({ ...trial("pref-30-vs-bad-60", top, bottom), motion });
    const answers = [
      { trial: at("fast", "30", "60-naive-4ms"), answer: "bottom" as const },
      { trial: at("fast", "60-naive-4ms", "30"), answer: "top" as const },
      { trial: at("slow", "30", "60-naive-4ms"), answer: "top" as const },
      { trial: at("slow", "60-naive-4ms", "30"), answer: "bottom" as const },
      { trial: at("normal", "30", "60-naive-4ms"), answer: "top" as const },
      { trial: at("normal", "60-naive-4ms", "30"), answer: "same" as const },
      { trial: trial("pacing-60", "60", "60-naive-4ms"), answer: "top" as const },
    ];
    expect(preferenceTally(answers)).toEqual([
      "Slow: perfect 30 fps ×2",
      "Normal: perfect 30 fps ×1, no difference ×1",
      "Fast: jittery 60 fps ×2",
    ]);
    expect(preferenceTally(answers.slice(6))).toEqual([]);
  });
});

describe("the result record", () => {
  const answers: AnsweredTrial[] = [
    { trial: trial("pacing-60", "60-naive-heavy", "60", 1), answer: "bottom", answerMs: 4321.6, health },
    { trial: trial("pref-30-vs-bad-60", "30", "60-naive-heavy", 2), answer: "top", answerMs: 2000, health },
  ];
  const record = buildRecord(answers, null, "abc123", new Date("2026-09-26T15:42:11Z"), "Mozilla/5.0 Chrome/140.0 Edg/140.0");

  it("is versioned and keeps the day only", () => {
    expect(record).toMatchObject({
      format: RESULT_FORMAT,
      testVersion: DEFINITIONS.testVersion,
      clipsHash: "abc123",
      date: "2026-09-26",
    });
    expect(JSON.stringify(record)).not.toMatch(/15:42|T\d\d:/);
  });

  it("records each answer by question id, with its correctness and playback", () => {
    expect(record.trials[0]).toEqual({
      id: "pacing-60-fast",
      category: "pacing",
      position: 1,
      motion: "fast",
      top: "60-naive-heavy",
      bottom: "60",
      answer: "bottom",
      correct: true,
      answerMs: 4322,
      playback: { presented: 480, offRhythm: 3 },
    });
    expect(record.trials[1]?.correct).toBeNull();
    expect(record.score.overall).toEqual({ correct: 1, of: 1 });
  });

  it("stores the browser family only", () => {
    expect(browserFamily("Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/140.0 Safari/537.36 Edg/140.0")).toBe("Edge");
    expect(browserFamily("Mozilla/5.0 Firefox/141.0")).toBe("Firefox");
    expect(browserFamily("Mozilla/5.0 AppleWebKit/537.36 Chrome/140.0 Safari/537.36")).toBe("Chrome");
    expect(browserFamily("Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15")).toBe("Safari");
  });
});
