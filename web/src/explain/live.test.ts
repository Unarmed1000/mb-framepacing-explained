import { describe, expect, it } from "vitest";

import type { VideoEntry } from "../manifest";
import { findClip, halfRows } from "./live";

const clip = (scene: string, top: string, bottom: string): VideoEntry =>
  ({ file: `${scene}-${top}-${bottom}.mp4`, scene, top: { mode: top }, bottom: { mode: bottom } }) as unknown as VideoEntry;

describe("findClip", () => {
  it("finds the single box clip with the given mode on top, never a row", () => {
    const videos = [
      clip("row", "60", "60-naive-heavy"),
      clip("box", "60-naive-heavy", "60"),
      clip("box", "60", "60-naive-heavy"),
    ];
    expect(findClip(videos, "60", "60-naive-heavy")?.file).toBe("box-60-60-naive-heavy.mp4");
    expect(findClip(videos, "30", "60")).toBeUndefined();
  });
});

describe("halfRows", () => {
  it("splits a clip at the divider the video tool draws, leaving the divider out", () => {
    // 384 high: a 2 px divider on rows 191-192; 720 high: a 4 px divider on rows 358-361
    expect(halfRows(384, "top")).toEqual({ from: 0, to: 191 });
    expect(halfRows(384, "bottom")).toEqual({ from: 194, to: 384 });
    expect(halfRows(720, "top")).toEqual({ from: 0, to: 358 });
    expect(halfRows(720, "bottom")).toEqual({ from: 363, to: 720 });
  });
});
