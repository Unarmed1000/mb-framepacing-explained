// SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
import { describe, expect, it } from "vitest";

import { cssSizeForDevicePixels, devicePixelBox, fitsAtDevicePixels, isOneToOne, snapOffset } from "./scaling";

const video = { width: 1280, height: 720 };

describe("cssSizeForDevicePixels", () => {
  it("sizes the video so it covers exactly 1280 x 720 device pixels", () => {
    for (const ratio of [1, 1.25, 1.5, 2]) {
      const size = cssSizeForDevicePixels(video, ratio);
      expect(size.width * ratio).toBeCloseTo(1280, 9);
      expect(size.height * ratio).toBeCloseTo(720, 9);
    }
    expect(cssSizeForDevicePixels(video, 1.25)).toEqual({ width: 1024, height: 576 });
  });
});

describe("snapOffset", () => {
  it("moves a position onto a whole device pixel", () => {
    for (const ratio of [1, 1.25, 1.5, 2]) {
      for (const position of [0, 10.3, 100.5, 333.33]) {
        const snapped = (position + snapOffset(position, ratio)) * ratio;
        expect(Math.abs(snapped - Math.round(snapped))).toBeLessThan(1e-9);
        expect(Math.abs(snapOffset(position, ratio))).toBeLessThanOrEqual(0.5 / ratio + 1e-9);
      }
    }
  });
});

describe("fitsAtDevicePixels", () => {
  it("compares the viewport in device pixels", () => {
    expect(fitsAtDevicePixels(video, { width: 1024, height: 600 }, 1.25)).toBe(true);
    expect(fitsAtDevicePixels(video, { width: 1024, height: 600 }, 1)).toBe(false);
    expect(fitsAtDevicePixels(video, { width: 1280, height: 719 }, 1)).toBe(false);
  });
});

describe("isOneToOne", () => {
  it("accepts exactly 1280 x 720 device pixels on whole device pixels", () => {
    expect(isOneToOne(devicePixelBox({ left: 80, top: 213, width: 1280, height: 720 }, 1), video)).toBe(true);
    expect(isOneToOne(devicePixelBox({ left: 64, top: 170.4, width: 1024, height: 576 }, 1.25), video)).toBe(true);
  });

  it("rejects a scaled video or one between device pixels", () => {
    expect(isOneToOne(devicePixelBox({ left: 80, top: 213, width: 1280, height: 720 }, 1.25), video)).toBe(false);
    expect(isOneToOne(devicePixelBox({ left: 80.5, top: 213, width: 1280, height: 720 }, 1), video)).toBe(false);
  });
});
