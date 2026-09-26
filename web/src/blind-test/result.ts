// The blind test's result: anonymised (the day only, no identifiers) and versioned, kept in the browser and exportable as JSON.

import type { ViewingReport } from "../checks/viewing";
import type { PlaybackHealth } from "../video/pixel-video";
import { DEFINITIONS, isCorrect, score, type Answer, type Category, type CategoryScore, type Trial } from "./trials";

/** The result schema's version: bump when the fields change. */
export const RESULT_FORMAT = 1;
const HISTORY_KEY = "mb-framepacing-explained.blind-test";
const HISTORY_LIMIT = 50;

export interface AnsweredTrial {
  trial: Trial;
  answer: Answer;
  answerMs: number;
  health: PlaybackHealth;
}

export interface TrialRecord {
  id: string;
  category: Category;
  position: number;
  motion: string;
  top: string;
  bottom: string;
  answer: Answer;
  correct: boolean | null;
  answerMs: number;
  playback: { presented: number; offRhythm: number };
}

export interface ResultRecord {
  format: number;
  testVersion: number;
  /** A hash of the clips' manifests: results made with different clips are never mixed. */
  clipsHash: string;
  /** The day only (UTC), no time. */
  date: string;
  viewing: {
    refreshHz: number | null;
    sixtyMultiple: number | null;
    irregularShare: number | null;
    devicePixelRatio: number;
    fullscreen: boolean;
    browser: string;
  } | null;
  trials: TrialRecord[];
  score: { overall: CategoryScore; byCategory: Partial<Record<Category, CategoryScore>> };
}

/** The browser family only, never the full user agent. */
export function browserFamily(userAgent: string): string {
  if (/Edg\//.test(userAgent)) return "Edge";
  if (/Firefox\//.test(userAgent)) return "Firefox";
  if (/Chrome\//.test(userAgent)) return "Chrome";
  if (/Safari\//.test(userAgent)) return "Safari";
  return "other";
}

export function buildRecord(
  answers: readonly AnsweredTrial[],
  viewing: ViewingReport | null,
  clipsHash: string,
  date: Date,
  userAgent: string,
): ResultRecord {
  return {
    format: RESULT_FORMAT,
    testVersion: DEFINITIONS.testVersion,
    clipsHash,
    date: date.toISOString().slice(0, 10),
    viewing: viewing && {
      refreshHz: viewing.refresh === null ? null : Math.round(viewing.refresh.hz * 100) / 100,
      sixtyMultiple: viewing.sixtyMultiple,
      irregularShare: viewing.refresh === null ? null : Math.round(viewing.refresh.irregularShare * 1000) / 1000,
      devicePixelRatio: viewing.devicePixelRatio,
      fullscreen: viewing.fullscreen,
      browser: browserFamily(userAgent),
    },
    trials: answers.map(({ trial, answer, answerMs, health }) => ({
      id: trial.id,
      category: trial.definition.category,
      position: trial.position,
      motion: trial.motion,
      top: trial.clip.video.top.mode,
      bottom: trial.clip.video.bottom.mode,
      answer,
      correct: isCorrect(trial, answer),
      answerMs: Math.round(answerMs),
      playback: { presented: health.presented, offRhythm: health.dropped + health.late + health.early },
    })),
    score: score(answers),
  };
}

/** A short, stable hash of the manifests' text (SHA-256, first 16 hex digits), or "unavailable" outside a secure context. */
export async function hashText(text: string): Promise<string> {
  if (!globalThis.crypto?.subtle) return "unavailable";
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)]
    .slice(0, 8)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

/** The visitor's earlier results in this browser (newest last); empty when storage is unavailable. */
export function loadHistory(): ResultRecord[] {
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    return stored ? (JSON.parse(stored) as ResultRecord[]) : [];
  } catch {
    return [];
  }
}

export function saveToHistory(record: ResultRecord): void {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify([...loadHistory(), record].slice(-HISTORY_LIMIT)));
  } catch {
    // Private windows and blocked storage: the result is still shown and can be downloaded
  }
}

export function downloadRecord(record: ResultRecord): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `frame-pacing-blind-test-${record.date}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
