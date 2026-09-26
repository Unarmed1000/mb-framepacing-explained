import { describe, expect, it } from "vitest";

import { classifyStep } from "./pixel-video";

const period = 1000 / 60;

describe("classifyStep", () => {
  it("accepts one frame period, with display timing noise", () => {
    expect(classifyStep(1, period, period)).toBe("on-time");
    expect(classifyStep(1, period * 1.2, period)).toBe("on-time");
    expect(classifyStep(1, period * 0.8, period)).toBe("on-time");
  });

  it("finds late and early frames", () => {
    expect(classifyStep(1, period * 2, period)).toBe("late");
    expect(classifyStep(1, period * 1.5, period)).toBe("late");
    expect(classifyStep(1, 0, period)).toBe("early");
    expect(classifyStep(1, period * 0.5, period)).toBe("early");
  });

  it("finds dropped frames from gaps in the presented count", () => {
    expect(classifyStep(2, period * 2, period)).toBe("dropped");
    expect(classifyStep(3, period, period)).toBe("dropped");
  });
});
