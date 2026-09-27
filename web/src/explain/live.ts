// A live comparison on an explanation slide: one clip at 1:1 device pixels and its animation error chart, whose playhead follows it.

import { folderFor } from "../blind-test/trials";
import { missingClips } from "../blind-test/warmup";
import { errorChart } from "../charts/error-chart";
import { frameChart } from "../charts/frame-chart";
import { loadManifest, type VideoEntry } from "../manifest";
import { playbackControls } from "../video/controls";
import { PixelVideo } from "../video/pixel-video";

/** The lane height of a single box's chart, in the chart's units (the pairs' charts use 92). */
const SINGLE_LANE_HEIGHT = 56;

/** The rendered videos' usual size and frame rate, as their generators make them. */
const RENDERED = { width: 1280, height: 384, fps: 60 };

/** The clip of a motion with `top` above and `bottom` below (the single box, never the rows). */
export function findClip(videos: readonly VideoEntry[], top: string, bottom: string): VideoEntry | undefined {
  return videos.find((video) => video.scene === "box" && video.top.mode === top && video.bottom.mode === bottom);
}

/** A clip at 1:1 device pixels with a caption and, unless `chart` is false, its animation error chart following it; with
 * `frames`, also a chart of how long each frame stays on screen; with `controls`, playback controls under it. */
export function liveComparison(
  motion: string,
  top: string,
  bottom: string,
  caption: string,
  chart = true,
  frames = false,
  controls = false,
): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "live";
  const folder = folderFor(motion);
  loadManifest(folder)
    .then((manifest) => {
      const video = findClip(manifest.videos, top, bottom);
      if (!video) throw new Error(`${folder}: no clip with ${top} on top and ${bottom} below`);
      const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
      const text = document.createElement("p");
      text.className = "live-caption";
      text.textContent = caption;
      const lanes = [
        { title: "Top", mode: video.top },
        { title: "Bottom", mode: video.bottom },
      ];
      const charts = [
        ...(chart ? [errorChart(lanes, video.frameCount, video.fps)] : []),
        ...(frames ? [frameChart(lanes, video.frameCount, video.fps)] : []),
      ];
      player.onFrame = (mediaTime) => {
        for (const each of charts) each.setTime(mediaTime);
      };
      const cards = charts.map((each) => {
        const card = document.createElement("div");
        card.className = "card chart-card";
        card.append(each.svg);
        return card;
      });
      const bar = controls ? [playbackControls(player, video.fps, video.frameCount)] : [];
      holder.replaceChildren(player.element, ...bar, text, ...cards, player.readout);
      player.play();
    })
    .catch((error: unknown) => holder.replaceChildren(missingClips(error)));
  return holder;
}

/** A rendered video (clips.json's "rendered", made by its generator in tools/frame_pacing_video): the whole frame at 1:1 device
 * pixels, with a caption; `height` when it is not the usual 384; with `controls`, playback controls under it. */
export function renderedClip(name: string, caption: string, height = RENDERED.height, controls = false): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "live";
  const src = `videos/rendered/${name}.mp4`;
  const player = new PixelVideo(src, { width: RENDERED.width, height }, RENDERED.fps, { label: caption });
  const text = document.createElement("p");
  text.className = "live-caption";
  text.textContent = caption;
  player.video.addEventListener("error", () => holder.replaceChildren(missingClips(new Error(`${src} is missing`))));
  holder.replaceChildren(player.element, text, player.readout);
  if (controls) {
    // Its length is known once the video's metadata is
    player.video.addEventListener(
      "loadedmetadata",
      () => {
        const frames = Math.round(player.video.duration * RENDERED.fps);
        player.element.after(playbackControls(player, RENDERED.fps, frames));
      },
      { once: true },
    );
  }
  player.play();
  return holder;
}

/** The video rows of one box's half, as the video tool lays it out (the divider in the middle, height / 180 thick, at least 1):
 * top from the first row to the divider, bottom from just below it (one row of margin, so no part of the divider shows) to the end. */
export function halfRows(height: number, half: "top" | "bottom"): { from: number; to: number } {
  const thickness = Math.max(1, Math.floor(height / 180));
  const divider = Math.floor((height - thickness) / 2);
  return half === "top" ? { from: 0, to: divider } : { from: divider + thickness + 1, to: height };
}

/** One box alone, at 1:1 device pixels, with a label under it: one half of the clip with `top` above and `bottom` below; with
 * `chart`, its animation error chart follows it. */
export function singleBox(
  motion: string,
  top: string,
  bottom: string,
  half: "top" | "bottom",
  label: string,
  chart = false,
): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "live single";
  const folder = folderFor(motion);
  loadManifest(folder)
    .then((manifest) => {
      const video = findClip(manifest.videos, top, bottom);
      if (!video) throw new Error(`${folder}: no clip with ${top} on top and ${bottom} below`);
      const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps, {
        rows: halfRows(video.height, half),
        label: `One box moving: ${label}`,
      });
      const text = document.createElement("p");
      text.className = "live-caption";
      text.textContent = label;
      holder.replaceChildren(player.element, text);
      if (chart) {
        // A lower lane than the pairs' charts: one box's chart under its video
        const lane = { title: "This box", mode: half === "top" ? video.top : video.bottom };
        const errors = errorChart([lane], video.frameCount, video.fps, SINGLE_LANE_HEIGHT);
        player.onFrame = (mediaTime) => errors.setTime(mediaTime);
        const card = document.createElement("div");
        card.className = "card chart-card";
        card.append(errors.svg);
        holder.append(card);
      }
      holder.append(player.readout);
      player.play();
    })
    .catch((error: unknown) => holder.replaceChildren(missingClips(error)));
  return holder;
}
