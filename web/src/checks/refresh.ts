// The display's refresh rate, estimated from requestAnimationFrame intervals, and whether it suits the 60 fps clips.

/** How far an interval may be from the median and still count as a regular refresh (share of the median). */
const REGULAR_TOLERANCE = 0.25;
/** How far a rate may be from a whole multiple of 60 Hz (share of that multiple); 59.94 Hz is 0.1 % off. */
const SIXTY_TOLERANCE = 0.015;
/** Fewer intervals than this give no estimate. */
const MIN_SAMPLES = 20;

export interface RefreshEstimate {
  /** The refresh rate in Hz, from the mean of the regular intervals. */
  hz: number;
  /** The mean regular interval in ms. */
  intervalMs: number;
  /** The share of intervals that are not regular: missed refreshes, a changing (VRR) rate, a throttled tab. */
  irregularShare: number;
  samples: number;
}

export function median(values: readonly number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  const upper = sorted[middle] ?? Number.NaN;
  return sorted.length % 2 === 1 ? upper : ((sorted[middle - 1] ?? Number.NaN) + upper) / 2;
}

/** Estimate the refresh rate from frame intervals in ms, or null when there are too few. */
export function estimateRefresh(intervalsMs: readonly number[]): RefreshEstimate | null {
  const valid = intervalsMs.filter((value) => Number.isFinite(value) && value > 0);
  if (valid.length < MIN_SAMPLES) return null;
  const middle = median(valid);
  const regular = valid.filter((value) => Math.abs(value - middle) <= middle * REGULAR_TOLERANCE);
  const intervalMs = regular.reduce((sum, value) => sum + value, 0) / regular.length;
  return {
    hz: 1000 / intervalMs,
    intervalMs,
    irregularShare: 1 - regular.length / valid.length,
    samples: valid.length,
  };
}

/** The whole multiple of 60 Hz the rate is (1 for 60 or 59.94 Hz, 2 for 120 Hz, ...), or null when it is none (50, 75, 144 Hz). */
export function sixtyMultiple(hz: number): number | null {
  const multiple = Math.round(hz / 60);
  if (multiple < 1) return null;
  return Math.abs(hz - 60 * multiple) <= 60 * multiple * SIXTY_TOLERANCE ? multiple : null;
}
