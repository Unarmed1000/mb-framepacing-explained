import { describe, expect, it } from "vitest";

import { refreshesOnScreen } from "./frame-chart";

describe("refreshesOnScreen", () => {
  it("counts the refreshes to the next frame, the last one's to the first frame of the next loop", () => {
    // Full rate, one frame held for two refreshes, then half rate; a 10-refresh clip that starts at refresh 0
    expect(refreshesOnScreen([0, 1, 3, 4, 6, 8], 10)).toEqual([1, 2, 1, 2, 2, 2]);
  });

  it("wraps to a first frame that is not on refresh 0", () => {
    expect(refreshesOnScreen([1, 3], 4)).toEqual([2, 2]);
  });
});
