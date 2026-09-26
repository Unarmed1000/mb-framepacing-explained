import { describe, expect, it } from "vitest";

import type { VideoEntry } from "../manifest";
import { findClip } from "./live";

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
