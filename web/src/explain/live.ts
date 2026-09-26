// A live comparison on an explanation slide: one clip at 1:1 device pixels and its animation error chart, whose playhead follows it.

import { folderFor } from "../blind-test/trials";
import { missingClips } from "../blind-test/warmup";
import { errorChart } from "../charts/error-chart";
import { loadManifest, type VideoEntry } from "../manifest";
import { PixelVideo } from "../video/pixel-video";

/** The clip of a motion with `top` above and `bottom` below (the single box, never the rows). */
export function findClip(videos: readonly VideoEntry[], top: string, bottom: string): VideoEntry | undefined {
  return videos.find((video) => video.scene === "box" && video.top.mode === top && video.bottom.mode === bottom);
}

export function liveComparison(motion: string, top: string, bottom: string, caption: string): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "live";
  const folder = folderFor(motion);
  loadManifest(folder)
    .then((manifest) => {
      const video = findClip(manifest.videos, top, bottom);
      if (!video) throw new Error(`${folder}: no clip with ${top} on top and ${bottom} below`);
      const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps);
      const chart = errorChart(
        [
          { title: "Top", mode: video.top },
          { title: "Bottom", mode: video.bottom },
        ],
        video.frameCount,
        video.fps,
      );
      player.onFrame = (mediaTime) => chart.setTime(mediaTime);
      const text = document.createElement("p");
      text.className = "live-caption";
      text.textContent = caption;
      const card = document.createElement("div");
      card.className = "card chart-card";
      card.append(chart.svg);
      holder.replaceChildren(player.element, text, card, player.readout);
      player.play();
    })
    .catch((error: unknown) => holder.replaceChildren(missingClips(error)));
  return holder;
}

/** Video rows above the divider line, where the top box moves (as the video tool lays it out: the divider is height / 180 thick,
 * at least 1, in the middle). */
export function rowsAboveDivider(height: number): number {
  const thickness = Math.max(1, Math.floor(height / 180));
  return Math.floor((height - thickness) / 2);
}

/** One box alone: the top half of a clip with `mode` in both halves, at 1:1 device pixels, with a label under it. */
export function singleBox(motion: string, mode: string, label: string): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "live single";
  const folder = folderFor(motion);
  loadManifest(folder)
    .then((manifest) => {
      const video = findClip(manifest.videos, mode, mode);
      if (!video) throw new Error(`${folder}: no clip with ${mode} in both halves`);
      const player = new PixelVideo(`${folder}/${video.file}`, { width: video.width, height: video.height }, video.fps, {
        visibleRows: rowsAboveDivider(video.height),
        label: `One box moving: ${label}`,
      });
      const text = document.createElement("p");
      text.className = "live-caption";
      text.textContent = label;
      holder.replaceChildren(player.element, text, player.readout);
      player.play();
    })
    .catch((error: unknown) => holder.replaceChildren(missingClips(error)));
  return holder;
}
