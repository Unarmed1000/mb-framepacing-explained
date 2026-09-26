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

/** A clip at 1:1 device pixels with a caption and, unless `chart` is false, its animation error chart following it. */
export function liveComparison(motion: string, top: string, bottom: string, caption: string, chart = true): HTMLElement {
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
      if (chart) {
        const errors = errorChart(
          [
            { title: "Top", mode: video.top },
            { title: "Bottom", mode: video.bottom },
          ],
          video.frameCount,
          video.fps,
        );
        player.onFrame = (mediaTime) => errors.setTime(mediaTime);
        const card = document.createElement("div");
        card.className = "card chart-card";
        card.append(errors.svg);
        holder.replaceChildren(player.element, text, card, player.readout);
      } else holder.replaceChildren(player.element, text, player.readout);
      player.play();
    })
    .catch((error: unknown) => holder.replaceChildren(missingClips(error)));
  return holder;
}

/** The video rows of one box's half, as the video tool lays it out (the divider in the middle, height / 180 thick, at least 1):
 * top from the first row to the divider, bottom from just below it (one row of margin, so no part of the divider shows) to the end. */
export function halfRows(height: number, half: "top" | "bottom"): { from: number; to: number } {
  const thickness = Math.max(1, Math.floor(height / 180));
  const divider = Math.floor((height - thickness) / 2);
  return half === "top" ? { from: 0, to: divider } : { from: divider + thickness + 1, to: height };
}

/** One box alone, at 1:1 device pixels, with a label under it: one half of the clip with `top` above and `bottom` below. */
export function singleBox(motion: string, top: string, bottom: string, half: "top" | "bottom", label: string): HTMLElement {
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
      holder.replaceChildren(player.element, text, player.readout);
      player.play();
    })
    .catch((error: unknown) => holder.replaceChildren(missingClips(error)));
  return holder;
}
