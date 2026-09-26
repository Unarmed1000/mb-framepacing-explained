// Animation error per frame as signed bars, one lane per half of the video, with a playhead that follows playback.
// Same design as the SVG diagrams of tools/timing_diagrams (the dark grey card, the colours).

import type { ModeEntry } from "../manifest";

const SVG = "http://www.w3.org/2000/svg";
const WIDTH = 1200;
const LEFT = 70;
const RIGHT = 24;
const LANE_H = 92;
const TOP = 58;
const GAP = 52;

export interface Lane {
  title: string;
  mode: ModeEntry;
}

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

export interface ErrorChart {
  svg: SVGSVGElement;
  /** Move the playhead to the video's media time (s). */
  setTime(mediaTime: number): void;
}

/** A chart of both halves' animation error on one shared scale; `refreshes` is the clip length in output refreshes. */
export function errorChart(lanes: readonly Lane[], refreshes: number, fps: number): ErrorChart {
  const height = TOP + lanes.length * LANE_H + (lanes.length - 1) * GAP + 36;
  const svg = element("svg", { viewBox: `0 0 ${WIDTH} ${height}`, class: "error-chart", role: "img" });
  svg.setAttribute("aria-label", "Animation error per frame of the top and the bottom half");
  const plotWidth = WIDTH - LEFT - RIGHT;
  const x = (refresh: number): number => LEFT + (refresh / refreshes) * plotWidth;
  const largest = Math.max(1, ...lanes.flatMap((lane) => lane.mode.frames.animationErrorMs.map(Math.abs)));
  const limit = Math.ceil(largest * 1.15);
  svg.append(
    label(LEFT, 20, "ANIMATION ERROR PER FRAME", "chart-label"),
    label(WIDTH - RIGHT, 20, "+ shown too soon, − shown too late", "chart-note", "end"),
  );

  lanes.forEach((lane, index) => {
    const top = TOP + index * (LANE_H + GAP);
    const zero = top + LANE_H / 2;
    const y = (value: number): number => zero - (value / limit) * (LANE_H / 2);
    // The lane's title and mode on a line of their own above it, so a long mode name never runs into the bars
    const heading = label(LEFT, top - 12, lane.title, "chart-lane");
    const mode = document.createElementNS(SVG, "tspan");
    mode.setAttribute("class", "chart-note");
    mode.textContent = ` · ${lane.mode.label}`;
    heading.append(mode);
    svg.append(heading);
    for (const value of [limit, -limit]) {
      svg.append(element("line", { x1: LEFT, x2: WIDTH - RIGHT, y1: y(value), y2: y(value), class: "chart-grid" }));
      svg.append(label(LEFT - 8, y(value) + 4, `${value > 0 ? "+" : "−"}${Math.abs(value)} ms`, "chart-note", "end"));
    }
    const { refresh, animationErrorMs } = lane.mode.frames;
    const barWidth = Math.max(1, plotWidth / refreshes - 0.4);
    animationErrorMs.forEach((value, frame) => {
      if (Math.abs(value) < 1e-9) return;
      const at = refresh[frame] ?? 0;
      const [y0, y1] = [zero, y(value)].sort((a, b) => a - b) as [number, number];
      svg.append(element("rect", { x: x(at), y: y0, width: barWidth, height: Math.max(0.8, y1 - y0), class: "chart-bar" }));
    });
    svg.append(element("line", { x1: LEFT, x2: WIDTH - RIGHT, y1: zero, y2: zero, class: "chart-zero" }));
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
