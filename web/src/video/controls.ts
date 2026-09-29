// SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Playback controls under a video: play and pause, the speed (1x, 1/2x, 1/4x), stepping a frame back or forward, and a slider
// to move back and forth through the clip. At a lower speed each video frame stays on screen longer, so the pacing it shows is
// the same, only slower. Used where a slide asks for them (`controls` on its video line).

import type { PixelVideo } from "./pixel-video";

const SPEEDS = [1, 0.5, 0.25] as const;

/** The video frame shown at media time `time` (s) of a clip of `frames` frames at `fps`. */
export function frameAt(time: number, fps: number, frames: number): number {
  // A frame's start can come back a hair early from the video (its time base): a small tolerance keeps it in its own frame
  return Math.min(frames - 1, Math.max(0, Math.floor(time * fps + 0.02)));
}

/** The media time (s) to seek to for video frame `frame`: its middle, so the browser shows exactly that frame. */
export function timeOf(frame: number, fps: number): number {
  return (frame + 0.5) / fps;
}

function button(text: string, label: string): HTMLButtonElement {
  const node = document.createElement("button");
  node.type = "button";
  node.className = "control";
  node.textContent = text;
  node.setAttribute("aria-label", label);
  node.title = label;
  return node;
}

/** The controls for `player`, a clip of `frames` frames at `fps`. */
export function playbackControls(player: PixelVideo, fps: number, frames: number): HTMLElement {
  const video = player.video;
  const bar = document.createElement("div");
  bar.className = "playback";
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Playback");

  const back = button("⏮", "One frame back");
  const toggle = button("⏸", "Pause");
  const forward = button("⏭", "One frame forward");
  const speeds = SPEEDS.map((speed) => {
    const node = button(
      speed === 1 ? "1×" : speed === 0.5 ? "½×" : "¼×",
      `Play at ${speed === 1 ? "full" : `${speed * 100} %`} speed`,
    );
    node.classList.add("speed");
    node.setAttribute("aria-pressed", String(speed === 1));
    node.addEventListener("click", () => {
      video.playbackRate = speed;
      for (const [index, other] of speeds.entries()) other.setAttribute("aria-pressed", String(SPEEDS[index] === speed));
    });
    return node;
  });
  const slider = document.createElement("input");
  Object.assign(slider, { type: "range", min: "0", max: String(frames - 1), step: "1", value: "0" });
  slider.className = "scrub";
  slider.setAttribute("aria-label", "Position in the clip");
  const time = document.createElement("span");
  time.className = "playback-time";

  // The frame on screen, as the video last reported it: its clock runs a little ahead of that
  let shown = 0;
  const show = (frame: number): void => {
    shown = frame;
    slider.value = String(frame);
    time.textContent = `${(frame / fps).toFixed(2)} s · frame ${frame + 1} of ${frames}`;
  };
  const seek = (frame: number): void => {
    player.pause();
    const wrapped = ((frame % frames) + frames) % frames;
    video.currentTime = timeOf(wrapped, fps);
    show(wrapped);
  };
  const current = (): number => shown;
  const setPlaying = (): void => {
    const paused = video.paused;
    toggle.textContent = paused ? "▶" : "⏸";
    toggle.setAttribute("aria-label", paused ? "Play" : "Pause");
    toggle.title = paused ? "Play" : "Pause";
  };

  toggle.addEventListener("click", () => (video.paused ? player.playNow() : player.pause()));
  back.addEventListener("click", () => seek(current() - 1));
  forward.addEventListener("click", () => seek(current() + 1));
  slider.addEventListener("input", () => seek(Number(slider.value)));
  video.addEventListener("play", setPlaying);
  video.addEventListener("pause", setPlaying);
  player.addFrameListener((mediaTime) => show(frameAt(mediaTime, fps, frames)));
  // With focus in the controls, the keys work the video, not the slides: space plays or pauses, the arrows step a frame
  bar.addEventListener("keydown", (event) => {
    if (event.key === " " && event.target !== slider) {
      event.preventDefault();
      toggle.click();
    } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      seek(current() + (event.key === "ArrowLeft" ? -1 : 1));
    } else return;
    event.stopPropagation();
  });

  const group = (...nodes: HTMLElement[]): HTMLElement => {
    const span = document.createElement("span");
    span.className = "playback-group";
    span.append(...nodes);
    return span;
  };
  bar.append(group(back, toggle, forward), group(...speeds), slider, time);
  show(0);
  setPlaying();
  return bar;
}
