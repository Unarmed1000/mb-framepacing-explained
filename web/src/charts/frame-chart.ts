// How long each frame stays on screen (its display time step), one lane per half of the video, as steps: in green, or in red when it
// stays longer than planned because the next frame came late, with a playhead that follows playback. The same card and scale conventions as the animation error chart.

import type { Lane } from "./error-chart";

const SVG = "http://www.w3.org/2000/svg";
const WIDTH = 1200;
const LEFT = 70;
const RIGHT = 24;
const LANE_H = 92;
const TOP = 58;
const GAP = 52;

function element<K extends keyof SVGElementTagNameMap>(
  name: K,
  attributes: Record<string, string | number>,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function label(x: number, y: number, content: string, className: string, anchor = "start"): SVGTextElement {
  const node = element("text", { x, y, class: className, "text-anchor": anchor });
  node.textContent = content;
  return node;
}

export interface FrameChart {
  svg: SVGSVGElement;
  /** Move the playhead to the video's media time (s). */
  setTime(mediaTime: number): void;
}

/** Each frame's time on screen, in refreshes: from the refresh it is shown on to the next frame's (the last one's runs to the
 * first frame of the next loop). */
export function refreshesOnScreen(refresh: readonly number[], refreshes: number): number[] {
  return refresh.map((at, index) => (refresh[index + 1] ?? refreshes + (refresh[0] ?? 0)) - at);
}

/** Whether each frame stays on screen longer than planned, at the rate the game is aiming for: the next frame is late (`late`,
 * refreshes after the one each was rendered for), so the display holds this one. A frame of a 60 Hz game held for 33.3 ms is one,
 * however the game planned its next frame after a miss; one of a steady half rate is not. The last frame's next is the first
 * frame of the next loop. */
export function heldTooLong(late: readonly number[]): boolean[] {
  return late.map((_, index) => (late[index + 1] ?? late[0] ?? 0) > 0);
}

/** A chart of the lanes' display time steps on one shared scale; `refreshes` is the clip length in output refreshes. */
export function frameChart(lanes: readonly Lane[], refreshes: number, fps: number): FrameChart {
  const height = TOP + lanes.length * LANE_H + (lanes.length - 1) * GAP + 36;
  const svg = element("svg", { viewBox: `0 0 ${WIDTH} ${height}`, class: "error-chart frame-chart", role: "img" });
  svg.setAttribute("aria-label", "How long each frame of the top and the bottom half stays on screen");
  const plotWidth = WIDTH - LEFT - RIGHT;
  const x = (refresh: number): number => LEFT + (refresh / refreshes) * plotWidth;
  const refreshMs = 1000 / fps;
  const onScreen = lanes.map((lane) => refreshesOnScreen(lane.mode.frames.refresh, refreshes));
  const longest = Math.max(2, ...onScreen.flat());
  const limit = (longest + 0.5) * refreshMs;
  svg.append(
    label(LEFT, 20, "DISPLAY TIME STEP: HOW LONG EACH FRAME IS ON SCREEN", "chart-label"),
    label(WIDTH - RIGHT, 20, "green as planned, red held too long", "chart-note", "end"),
  );

  lanes.forEach((lane, index) => {
    const top = TOP + index * (LANE_H + GAP);
    const base = top + LANE_H;
    const y = (ms: number): number => base - (ms / limit) * LANE_H;
    const heading = label(LEFT, top - 12, lane.title, "chart-lane");
    if (!lane.hideMode) {
      const mode = document.createElementNS(SVG, "tspan");
      mode.setAttribute("class", "chart-note");
      mode.textContent = ` · ${lane.mode.label}`;
      heading.append(mode);
    }
    svg.append(heading);
    // A line per whole number of refreshes: 16.7 ms, 33.3 ms at 60 Hz
    for (let count = 1; count <= longest; count++) {
      const ms = count * refreshMs;
      svg.append(element("line", { x1: LEFT, x2: WIDTH - RIGHT, y1: y(ms), y2: y(ms), class: "chart-grid" }));
      svg.append(label(LEFT - 8, y(ms) + 4, `${ms.toFixed(1)} ms`, "chart-note", "end"));
    }
    svg.append(element("line", { x1: LEFT, x2: WIDTH - RIGHT, y1: base, y2: base, class: "chart-zero" }));
    const { refresh, late } = lane.mode.frames;
    const held = heldTooLong(late);
    const steps = onScreen[index] ?? [];
    steps.forEach((count, frame) => {
      const at = refresh[frame] ?? 0;
      const level = y(count * refreshMs);
      svg.append(
        element("line", {
          x1: x(at),
          x2: x(Math.min(refreshes, at + count)),
          y1: level,
          y2: level,
          class: held[frame] ? "chart-step late" : "chart-step",
        }),
      );
      const next = steps[frame + 1];
      if (next !== undefined && next !== count) {
        const end = x(at + count);
        svg.append(element("line", { x1: end, x2: end, y1: level, y2: y(next * refreshMs), class: "chart-riser" }));
      }
    });
  });

  const bottom = height - 20;
  for (let second = 0; second <= refreshes / fps; second++) {
    svg.append(label(x(second * fps), bottom + 14, `${second} s`, "chart-note", "middle"));
  }
  const playhead = element("line", { x1: LEFT, x2: LEFT, y1: TOP - 6, y2: bottom - 8, class: "chart-playhead" });
  svg.append(playhead);
  return {
    svg,
    setTime(mediaTime: number): void {
      const refresh = (Math.floor(mediaTime * fps + 1e-6) % refreshes) + 0.5;
      playhead.setAttribute("x1", String(x(refresh)));
      playhead.setAttribute("x2", String(x(refresh)));
    },
  };
}
