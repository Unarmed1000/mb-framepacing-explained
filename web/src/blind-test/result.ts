// SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// The blind test's result: anonymised (the day only, no identifiers) and versioned, kept in the browser and exportable as JSON.

import type { ViewingReport } from "../checks/viewing";
import type { PlaybackHealth } from "../video/pixel-video";
import {
  allWarmups,
  DEFINITIONS,
  isCorrect,
  score,
  type Answer,
  type Category,
  type CategoryScore,
  type ClipLibrary,
  type Definitions,
  type Trial,
  type TrialDefinition,
} from "./trials";

/** The result schema's version: bump when the fields change. 2: the playback also keeps dropped, late and early. */
export const RESULT_FORMAT = 2;
const HISTORY_KEY = "mb-framepacing-explained.blind-test";
const HISTORY_LIMIT = 50;

/** The playback of an answer saved in format 1, which kept only how many video frames were off the rhythm, not which way. */
export interface SavedPlayback {
  presented: number;
  offRhythm: number;
}

export interface AnsweredTrial {
  trial: Trial;
  answer: Answer;
  answerMs: number;
  health: PlaybackHealth | SavedPlayback;
  /** A saved answer shown with today's version of its question's clip, as the one it was asked with no longer exists. */
  similar?: boolean;
}

/** How many video frames were off the 60 fps rhythm: dropped, late or early. */
export const offRhythm = (health: PlaybackHealth | SavedPlayback): number =>
  "offRhythm" in health ? health.offRhythm : health.dropped + health.late + health.early;

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
  /** Format 2 and later also keep dropped, late and early. */
  playback: { presented: number; offRhythm: number; dropped?: number; late?: number; early?: number };
}

export interface ResultRecord {
  format: number;
  testVersion: number;
  /** Which of the tests (TestDefinition id); absent in results from before there was a choice. */
  test?: string;
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
  test?: string,
): ResultRecord {
  return {
    format: RESULT_FORMAT,
    testVersion: DEFINITIONS.testVersion,
    ...(test === undefined ? {} : { test }),
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
      playback:
        "offRhythm" in health
          ? { presented: health.presented, offRhythm: health.offRhythm }
          : {
              presented: health.presented,
              offRhythm: offRhythm(health),
              dropped: health.dropped,
              late: health.late,
              early: health.early,
            },
    })),
    score: score(answers),
  };
}

/** A saved answer's playback: the full split when the result kept it (format 2), else only the total. */
function savedHealth(playback: TrialRecord["playback"]): PlaybackHealth | SavedPlayback {
  const { presented, offRhythm, dropped, late, early } = playback;
  return dropped === undefined ? { presented, offRhythm } : { presented, dropped, late: late ?? 0, early: early ?? 0 };
}

/** A saved result's answers as questions again, with their clips, to show it like a result just taken; null when a question
 * no longer matches the trial definitions or its clip is missing (a result of an earlier test version). */
export function restoreAnswers(
  record: ResultRecord,
  library: ClipLibrary,
  definitions: Definitions = DEFINITIONS,
): AnsweredTrial[] | null {
  // Every question exactly as it was asked: none gone, none shown with today's clip instead
  const answers = restoreEach(record, library, definitions);
  return answers.every((answer) => answer !== null && !answer.similar) ? (answers as AnsweredTrial[]) : null;
}

/** Each of a saved result's answers as a question again, or null where its trial or clip no longer exists (changed in a later
 * test version): so what still exists can be watched again. */
export function restoreEach(
  record: ResultRecord,
  library: ClipLibrary,
  definitions: Definitions = DEFINITIONS,
): (AnsweredTrial | null)[] {
  return record.trials.map((saved) => restoreOne(saved, library, definitions));
}

function restoreOne(saved: TrialRecord, library: ClipLibrary, definitions: Definitions): AnsweredTrial | null {
  const modes = [saved.top, saved.bottom].sort().join(":");
  let definition: TrialDefinition | undefined;
  if (saved.category === "warm-up") {
    for (const warmup of allWarmups(definitions)) {
      const pair = warmup.pairs.find((each) => [...each].sort().join(":") === modes);
      if (pair && !definition)
        definition = { id: "warm-up", category: "warm-up", a: pair[0], b: pair[1], smoother: warmup.smoother };
    }
  } else {
    definition = definitions.trials.find(
      (trial) =>
        trial.category === saved.category &&
        [trial.a, trial.b].sort().join(":") === modes &&
        (saved.id === `${trial.id}-${saved.motion}` || saved.id === `${trial.id}-${saved.motion}-top-${saved.top}`),
    );
  }
  const clip = library.find(saved.motion, saved.top, saved.bottom);
  const answer = { answer: saved.answer, answerMs: saved.answerMs, health: savedHealth(saved.playback) };
  if (definition && clip)
    return { trial: { definition, id: saved.id, position: saved.position, motion: saved.motion, clip }, ...answer };
  // Its clip is gone: today's question like it, in the same category and with the same perfect half, its other half on the same
  // side (each pair is a flawed 60 against a perfect rate, or the same clip twice, so the flawed one is what changes)
  const similar = similarQuestion(saved, definitions);
  const today = similar && library.find(saved.motion, similar.top, similar.bottom);
  if (!similar || !today) return null;
  return {
    trial: { definition: similar.definition, id: saved.id, position: saved.position, motion: saved.motion, clip: today },
    ...answer,
    similar: true,
  };
}

/** Today's question like a saved one whose clip is gone: in its category and asked at its movement, keeping the saved half that
 * one of its modes still is (the one with the question's id first), and the other half on the same side; null when there is
 * none. */
function similarQuestion(
  saved: TrialRecord,
  definitions: Definitions,
): { definition: TrialDefinition; top: string; bottom: string } | null {
  if (saved.category === "warm-up") return null;
  const halves = [saved.top, saved.bottom];
  const candidates = definitions.trials.filter(
    (trial) =>
      trial.category === saved.category &&
      trial.a !== trial.b &&
      (trial.motions ?? definitions.motions).includes(saved.motion) &&
      halves.some((half) => half === trial.a || half === trial.b),
  );
  const definition = candidates.find((trial) => saved.id.startsWith(`${trial.id}-${saved.motion}`)) ?? candidates[0];
  if (!definition) return null;
  const kept = halves.find((half) => half === definition.a || half === definition.b)!;
  const other = kept === definition.a ? definition.b : definition.a;
  return { definition, top: saved.top === kept ? kept : other, bottom: saved.bottom === kept ? kept : other };
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
