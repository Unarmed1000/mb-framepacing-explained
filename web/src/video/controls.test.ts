import { describe, expect, it } from "vitest";

import { frameAt, timeOf } from "./controls";

describe("frameAt and timeOf", () => {
  it("finds the frame shown at a media time, within the clip", () => {
    expect(frameAt(0, 60, 480)).toBe(0);
    expect(frameAt(1, 60, 480)).toBe(60);
    expect(frameAt(8.5, 60, 480)).toBe(479);
    expect(frameAt(-1, 60, 480)).toBe(0);
  });

  it("seeks to the middle of a frame, which frameAt maps back to it", () => {
    for (const frame of [0, 1, 59, 60, 479]) expect(frameAt(timeOf(frame, 60), 60, 480)).toBe(frame);
  });
});
