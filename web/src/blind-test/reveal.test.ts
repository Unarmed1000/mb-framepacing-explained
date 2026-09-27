import { describe, expect, it } from "vitest";

import { choiceName } from "./reveal";

describe("choiceName", () => {
  it("names a mode in a few words, the late frame clips as such, not as perfect", () => {
    expect(choiceName("30")).toBe("perfect 30 fps");
    expect(choiceName("60-naive-4ms")).toBe("jittery 60 fps");
    expect(choiceName("60-diagram-slow-frames-every-1s")).toBe("60 fps with late frames");
    expect(choiceName("60-diagram-slow-frames-3x-every-1s")).toBe("60 fps with late frames");
    expect(choiceName("60-busy-swappy")).toBe("60 fps adapting its rate");
    expect(choiceName("60-busy-full-rate")).toBe("60 fps with late frames in a busy stretch");
  });
});
