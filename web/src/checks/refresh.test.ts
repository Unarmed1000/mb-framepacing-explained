import { describe, expect, it } from "vitest";

import { estimateRefresh, median, sixtyMultiple } from "./refresh";

const steady = (hz: number, count = 120): number[] => Array.from({ length: count }, () => 1000 / hz);

describe("median", () => {
  it("takes the middle value, or the mean of the two middle values", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 3, 2])).toBe(2.5);
  });
});

describe("estimateRefresh", () => {
  it("finds 60, 59.94, 120 and 144 Hz", () => {
    expect(estimateRefresh(steady(60))?.hz).toBeCloseTo(60, 6);
    expect(estimateRefresh(steady(60000 / 1001))?.hz).toBeCloseTo(59.94, 2);
    expect(estimateRefresh(steady(120))?.hz).toBeCloseTo(120, 6);
    expect(estimateRefresh(steady(144))?.hz).toBeCloseTo(144, 6);
  });

  it("ignores missed refreshes for the rate but counts them as irregular", () => {
    const intervals = steady(60, 100);
    for (let index = 0; index < 10; index++) intervals[index * 10] = 2000 / 60;
    const estimate = estimateRefresh(intervals);
    expect(estimate?.hz).toBeCloseTo(60, 6);
    expect(estimate?.irregularShare).toBeCloseTo(0.1, 6);
  });

  it("averages timer noise out", () => {
    const noisy = steady(60).map((value, index) => value + (index % 2 === 0 ? 0.4 : -0.4));
    expect(estimateRefresh(noisy)?.hz).toBeCloseTo(60, 6);
  });

  it("gives no estimate from too few or invalid intervals", () => {
    expect(estimateRefresh(steady(60, 5))).toBeNull();
    expect(estimateRefresh([...steady(60, 5), Number.NaN, -1, 0])).toBeNull();
  });
});

describe("sixtyMultiple", () => {
  it("accepts 60, 59.94, 120, 180 and 240 Hz", () => {
    expect(sixtyMultiple(60)).toBe(1);
    expect(sixtyMultiple(59.94)).toBe(1);
    expect(sixtyMultiple(120)).toBe(2);
    expect(sixtyMultiple(119.88)).toBe(2);
    expect(sixtyMultiple(180)).toBe(3);
    expect(sixtyMultiple(240)).toBe(4);
  });

  it("rejects rates that are not a whole multiple of 60 Hz", () => {
    for (const hz of [30, 50, 75, 90, 100, 144, 165]) expect(sixtyMultiple(hz)).toBeNull();
  });
});
