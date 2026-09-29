// SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
import { describe, expect, it } from "vitest";

import { heldTooLong, refreshesOnScreen } from "./frame-chart";

describe("refreshesOnScreen", () => {
  it("counts the refreshes to the next frame, the last one's to the first frame of the next loop", () => {
    // Full rate, one frame held for two refreshes, then half rate; a 10-refresh clip that starts at refresh 0
    expect(refreshesOnScreen([0, 1, 3, 4, 6, 8], 10)).toEqual([1, 2, 1, 2, 2, 2]);
  });

  it("wraps to a first frame that is not on refresh 0", () => {
    expect(refreshesOnScreen([1, 3], 4)).toEqual([2, 2]);
  });
});

describe("heldTooLong", () => {
  it("is the frame before a later one: the display holds it", () => {
    // A frame on time, the next one a refresh late, then on time again: the first is held
    expect(heldTooLong([0, 1, 0, 0])).toEqual([true, false, false, false]);
  });

  it("is every frame before a late one, in a run of misses too, and wraps to the next loop", () => {
    expect(heldTooLong([0, 1, 1, 0])).toEqual([true, true, false, false]);
    expect(heldTooLong([1, 0, 0])).toEqual([false, false, true]);
  });
});
