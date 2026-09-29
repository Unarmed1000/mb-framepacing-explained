// SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// The viewing check: measures the setup, reports each check with how to fix it, and re-runs when something changes.

import { estimateRefresh, sixtyMultiple, type RefreshEstimate } from "./refresh";
import { fitsAtDevicePixels, type Size } from "./scaling";

export type Status = "ok" | "warn" | "fail";

export interface CheckRow {
  id: string;
  label: string;
  status: Status;
  value: string;
  fix: string;
}

export interface ViewingReport {
  refresh: RefreshEstimate | null;
  sixtyMultiple: number | null;
  devicePixelRatio: number;
  pinchZoom: number;
  fits: boolean;
  videoFrameCallback: boolean;
  fullscreen: boolean;
  visible: boolean;
  rows: CheckRow[];
}

let latest: ViewingReport | null = null;

/** The most recent viewing check, from any check card, or null before the first one finished. */
export function latestViewingReport(): ViewingReport | null {
  return latest;
}

/** Up to this share of irregular frame intervals still counts as a stable refresh. */
const STABLE_SHARE = 0.05;

/** Collect requestAnimationFrame intervals for `durationMs`. A hidden tab gets no animation frames, so a timer ends the
 * measurement anyway, with what it has (too few intervals give no estimate). */
export function measureFrameIntervals(durationMs = 2000): Promise<number[]> {
  return new Promise((resolve) => {
    const intervals: number[] = [];
    let first: number | null = null;
    let last: number | null = null;
    let done = false;
    const finish = (): void => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve(intervals);
    };
    const timer = setTimeout(finish, durationMs + 1000);
    const step = (now: number): void => {
      if (done) return;
      if (last !== null) intervals.push(now - last);
      first ??= now;
      last = now;
      if (now - first < durationMs) requestAnimationFrame(step);
      else finish();
    };
    requestAnimationFrame(step);
  });
}

export async function runViewingCheck(video: Size): Promise<ViewingReport> {
  const refresh = estimateRefresh(await measureFrameIntervals());
  const multiple = refresh === null ? null : sixtyMultiple(refresh.hz);
  const devicePixelRatio = window.devicePixelRatio || 1;
  const pinchZoom = window.visualViewport?.scale ?? 1;
  const viewport = { width: window.innerWidth, height: window.innerHeight };
  const fits = fitsAtDevicePixels(video, viewport, devicePixelRatio);
  const videoFrameCallback = "requestVideoFrameCallback" in HTMLVideoElement.prototype;
  const fullscreen = document.fullscreenElement !== null;
  const visible = document.visibilityState === "visible";

  const rows: CheckRow[] = [];
  if (refresh === null) {
    rows.push({
      id: "refresh",
      label: "Refresh rate",
      status: "fail",
      value: "could not be measured",
      fix: "Keep this tab in front and visible while the check runs, then check again.",
    });
  } else {
    const hz = `${refresh.hz.toFixed(refresh.hz < 100 ? 2 : 1)} Hz`;
    rows.push(
      multiple === null
        ? {
            id: "refresh",
            label: "60 Hz compatible",
            status: "fail",
            value: `${hz}: not a multiple of 60`,
            fix: "Set the display to 60 Hz or a multiple (120, 180, 240 Hz) in the display settings. At other rates every clip judders, the perfect ones too.",
          }
        : {
            id: "refresh",
            label: "60 Hz compatible",
            status: "ok",
            value: multiple === 1 ? hz : `${hz}: each video frame shows for ${multiple} refreshes`,
            fix: "",
          },
      refresh.irregularShare <= STABLE_SHARE
        ? {
            id: "stable",
            label: "Stable refresh",
            status: "ok",
            value: `${pct(refresh.irregularShare)} irregular frames`,
            fix: "",
          }
        : {
            id: "stable",
            label: "Stable refresh",
            status: "warn",
            value: `${pct(refresh.irregularShare)} irregular frames`,
            fix: "Close heavy apps and other video tabs, plug a laptop in, and turn VRR (G-SYNC, FreeSync) off for the test.",
          },
    );
  }
  rows.push(
    pinchZoom !== 1
      ? {
          id: "scaling",
          label: "Scaling and zoom",
          status: "fail",
          value: `pinch zoom ${pinchZoom.toFixed(2)}x`,
          fix: "Pinch back out to 100 %.",
        }
      : !fits
        ? {
            id: "scaling",
            label: "Scaling and zoom",
            status: "fail",
            value: `window too small for ${video.width} x ${video.height} device pixels`,
            fix: "Use the browser's fullscreen (F11), or lower the browser zoom (Ctrl/Cmd and minus).",
          }
        : {
            id: "scaling",
            label: "Scaling and zoom",
            status: "ok",
            value: devicePixelRatio === 1 ? "1:1" : `1:1 (compensating a scale of ${pct(devicePixelRatio)})`,
            fix: "",
          },
    videoFrameCallback
      ? { id: "support", label: "Playback check", status: "ok", value: "supported", fix: "" }
      : {
          id: "support",
          label: "Playback check",
          status: "warn",
          value: "not supported by this browser",
          fix: "Use a current Chrome, Edge, Firefox or Safari, so dropped video frames can be detected.",
        },
    fullscreen
      ? { id: "fullscreen", label: "Fullscreen", status: "ok", value: "on", fix: "" }
      : {
          id: "fullscreen",
          label: "Fullscreen",
          status: "warn",
          value: "off",
          fix: "Recommended for the test: fewer distractions, and the browser composes less.",
        },
  );
  if (!visible) {
    rows.push({ id: "visible", label: "Tab visible", status: "fail", value: "hidden", fix: "Keep this tab in front." });
  }
  latest = { refresh, sixtyMultiple: multiple, devicePixelRatio, pinchZoom, fits, videoFrameCallback, fullscreen, visible, rows };
  return latest;
}

function pct(value: number): string {
  return `${Math.round(value * 100)} %`;
}

/** The overall status: the worst of the rows. */
export function overall(report: ViewingReport): Status {
  if (report.rows.some((row) => row.status === "fail")) return "fail";
  return report.rows.some((row) => row.status === "warn") ? "warn" : "ok";
}

/** A card showing the viewing check, measured now and again whenever zoom, window size, fullscreen or visibility changes. */
export function viewingCheckCard(video: Size, onReport?: (report: ViewingReport) => void): HTMLElement {
  const card = document.createElement("section");
  card.className = "card check-card";
  card.innerHTML = `
    <header class="check-head">
      <h2>Viewing check</h2>
      <span class="check-overall" data-status="pending">Measuring…</span>
    </header>
    <ul class="check-rows"></ul>
    <div class="check-actions">
      <button type="button" class="button" data-action="fullscreen">Fullscreen</button>
      <button type="button" class="button ghost" data-action="again">Check again</button>
    </div>`;
  const list = card.querySelector<HTMLUListElement>(".check-rows");
  const summary = card.querySelector<HTMLElement>(".check-overall");
  let running = false;
  let queued = false;

  const run = async (): Promise<void> => {
    if (running) {
      queued = true;
      return;
    }
    running = true;
    if (summary) {
      summary.dataset.status = "pending";
      summary.textContent = "Measuring…";
    }
    if (list && list.childElementCount === 0) {
      const waiting = document.createElement("li");
      waiting.className = "check-waiting";
      waiting.textContent = "Measuring the refresh rate for two seconds; keep this tab in front.";
      list.replaceChildren(waiting);
    }
    const report = await runViewingCheck(video);
    if (list) list.replaceChildren(...report.rows.map(renderRow));
    const status = overall(report);
    if (summary) {
      summary.dataset.status = status;
      summary.textContent = status === "ok" ? "Ready" : status === "warn" ? "Usable, see below" : "Fix before the test";
    }
    onReport?.(report);
    running = false;
    if (queued) {
      queued = false;
      void run();
    }
  };

  card.querySelector('[data-action="again"]')?.addEventListener("click", () => void run());
  card.querySelector('[data-action="fullscreen"]')?.addEventListener("click", () => {
    void (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
  });
  const rerun = (): void => void run();
  window.addEventListener("resize", rerun);
  window.visualViewport?.addEventListener("resize", rerun);
  document.addEventListener("fullscreenchange", rerun);
  document.addEventListener("visibilitychange", rerun);
  watchDevicePixelRatio(rerun);
  void run();
  return card;
}

function renderRow(row: CheckRow): HTMLLIElement {
  const item = document.createElement("li");
  item.className = "check-row";
  item.dataset.status = row.status;
  item.innerHTML = `<span class="dot" aria-hidden="true"></span><span class="check-label"></span><span class="check-value"></span>`;
  item.querySelector(".check-label")!.textContent = row.label;
  item.querySelector(".check-value")!.textContent = row.value;
  if (row.fix) {
    const fix = document.createElement("p");
    fix.className = "check-fix";
    fix.textContent = row.fix;
    item.append(fix);
  }
  return item;
}

/** Call `onChange` whenever the device pixel ratio changes (browser zoom, moving to a monitor with other scaling). */
export function watchDevicePixelRatio(onChange: () => void): void {
  const listen = (): void => {
    const query = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    query.addEventListener(
      "change",
      () => {
        onChange();
        listen();
      },
      { once: true },
    );
  };
  listen();
}
