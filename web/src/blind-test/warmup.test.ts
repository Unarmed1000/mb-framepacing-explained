import { describe, expect, it } from "vitest";

import type { ModeEntry, VideoEntry } from "../manifest";
import { isWarmup } from "./warmup";

const mode = (name: string, timer: "ideal" | "naive", noise: string | null): ModeEntry => ({
  mode: name,
  rate: 60,
  timer,
  noise,
  noiseWindowMs: noise === "window" ? 4 : null,
  label: name,
  frames: { refresh: [], animationErrorMs: [], dtMs: [], sampleMs: [], late: [] },
});

const perfect = mode("60", "ideal", null);
const window4 = mode("60-naive-4ms", "naive", "window");
const heavy = mode("60-naive-heavy", "naive", "heavy");

const video = (top: ModeEntry, bottom: ModeEntry): VideoEntry => ({
  file: `${top.mode}-${bottom.mode}.mp4`,
  speed: "fast",
  scene: "box",
  fps: 60,
  frameCount: 480,
  videoFrameCount: 480,
  width: 1280,
  height: 384,
  top,
  bottom,
});

describe("warm-up pairs", () => {
  it("are a perfect timer against a ±N ms window, in either order", () => {
    expect(isWarmup(video(perfect, window4))).toBe(true);
    expect(isWarmup(video(window4, perfect))).toBe(true);
  });

  it("are always a perfect 60 against a 60 Hz window", () => {
    const perfect30 = { ...perfect, mode: "30", rate: 30 };
    const window30 = { ...window4, mode: "30-naive-4ms", rate: 30 };
    expect(isWarmup(video(perfect30, window30))).toBe(false);
    expect(isWarmup(video(window30, perfect30))).toBe(false);
  });

  it("are always the fast movement", () => {
    expect(isWarmup({ ...video(perfect, window4), speed: "normal" })).toBe(false);
  });

  it("are never the rows", () => {
    expect(isWarmup({ ...video(perfect, window4), scene: "row", speed: "ui-384" })).toBe(false);
  });

  it("exclude the matrix's other pairs", () => {
    expect(isWarmup(video(perfect, heavy))).toBe(false);
    expect(isWarmup(video(perfect, perfect))).toBe(false);
    expect(isWarmup(video(window4, window4))).toBe(false);
  });
});
