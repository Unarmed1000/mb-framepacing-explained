// SPDX-FileCopyrightText: Copyright (C) 2026 Rene Thrane
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Each frame's verdict of every clip the page charts, as mb-framepacing measures it: verdicts.json, written by
// tools/timing_diagrams/generate_measured_charts.py --web-verdicts. Which frame is late and which is delta time jitter is
// mb-framepacing's rule; the page only draws it.

import data from "./verdicts.json";

/** One letter per frame of a clip: late, delta time jitter, within the error threshold, another error, none (verdicts.json's key). */
export type Verdict = "l" | "j" | "w" | "o" | "-";

const clips = data as unknown as Record<string, Record<string, string> | undefined>;

/** The verdicts of the clip of `mode` in `motion`, a letter per frame. Every clip the page charts has them (a test checks). */
export function verdictsFor(motion: string, mode: string): string {
  const verdicts = clips[motion]?.[mode];
  if (verdicts === undefined) {
    throw new Error(`no verdicts for ${mode} in ${motion}: run generate_measured_charts.py --web-verdicts`);
  }
  return verdicts;
}
