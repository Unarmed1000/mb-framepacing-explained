#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate the dynamic resolution chart (chart-dynamic-resolution.svg): the GPU time of each frame at 60 Hz, at a fixed resolution
and with dynamic resolution, as the load rises through a busy stretch and then jumps at a camera cut.

An illustration, not a measurement. The model is small and stated on the chart:
- a frame's GPU time is a part that does not scale with resolution (shadows, culling) plus a part that scales with the number of
  pixels, the square of the resolution scale;
- dynamic resolution picks each frame's scale from the GPU time of a frame rendered MEASURE_DELAY frames earlier (Unity reads GPU
  timing "with three frames delay"), aiming at the budget less some headroom, within a range of scales (Unreal's default is 50 to
  100 % of the screen), and never raising the scale by more than a step per frame, so it lowers the resolution fast and raises it
  slowly;
- a frame over the budget misses its refresh.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_dynamic_resolution.py [--output-dir DIR] [--png] [--background COLOUR]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
from dataclasses import dataclass
from pathlib import Path

from generate_diagrams import DEFAULT_OUTPUT_DIR, STYLE, find_browser, ms, save_png, text

REFRESH_MS = 1000 / 60
FRAMES = 120  # 2 s at 60 fps
FIXED_MS = 3.0  # GPU work that does not scale with resolution
MEASURE_DELAY = 3  # frames between rendering a frame and knowing its GPU time
HEADROOM = 0.1  # of the budget, left free to absorb small rises
MIN_SCALE = 0.5
MAX_SCALE = 1.0
MAX_RAISE = 0.02  # the most the scale rises per frame; it falls as far as it needs to at once


def load_ms(frame: int) -> float:
    """The GPU time a frame would take at full resolution: a light scene, a busy stretch building up and easing off, then a
    camera cut into an expensive view."""
    if frame < 20:
        return 12.0
    if frame < 45:
        return 12.0 + (frame - 20) / 25 * 9.0  # up to 21 ms
    if frame < 70:
        return 21.0
    if frame < 85:
        return 21.0 - (frame - 70) / 15 * 8.0  # back down to 13 ms
    if frame < 95:
        return 13.0
    if frame < 108:
        return 25.0  # the camera cut
    return 13.0


def gpu_ms(load: float, scale: float) -> float:
    """A frame's GPU time at a resolution scale (per axis): the fixed part, plus the rest by the number of pixels."""
    return FIXED_MS + (load - FIXED_MS) * scale * scale


@dataclass(frozen=True)
class Run:
    gpu: list[float]  # ms per frame
    scale: list[float]  # resolution scale per frame, 1 at full resolution


def fixed_run() -> Run:
    return Run([gpu_ms(load_ms(frame), 1.0) for frame in range(FRAMES)], [1.0] * FRAMES)


def dynamic_run() -> Run:
    target = REFRESH_MS * (1 - HEADROOM)
    gpu: list[float] = []
    scale: list[float] = []
    for frame in range(FRAMES):
        if frame < MEASURE_DELAY:
            chosen = MAX_SCALE
        else:
            # The latest frame whose GPU time is known: its full resolution load, from its time and its scale
            known = frame - MEASURE_DELAY
            full = FIXED_MS + (gpu[known] - FIXED_MS) / (scale[known] ** 2)
            wanted = ((target - FIXED_MS) / (full - FIXED_MS)) ** 0.5 if full > target else MAX_SCALE
            chosen = min(max(wanted, MIN_SCALE), MAX_SCALE, scale[-1] + MAX_RAISE)
        scale.append(chosen)
        gpu.append(gpu_ms(load_ms(frame), chosen))
    return Run(gpu, scale)


WIDTH = 1180
PLOT_X0 = 110
PLOT_X1 = WIDTH - 125
LANE_TOP = 118
PLOT_H = 150
LANE_H = 24 + PLOT_H + 58
TOP_MS = 30.0

CHART_STYLE = """
  .grid { stroke: #ffffff; stroke-opacity: 0.1; stroke-width: 1; }
  .ok { fill: #2ea043; }
  .miss { fill: #e5534b; }
  .budget { stroke: #d29922; stroke-width: 1.5; stroke-dasharray: 6 4; }
  .budget-text { fill: #d29922; font-size: 12px; }
  .scale { stroke: #58a6ff; stroke-width: 2; fill: none; stroke-linejoin: round; }
  .scale-text { fill: #58a6ff; font-size: 12px; }
"""


def render(background: str | None) -> str:
    lanes = [("Fixed resolution", fixed_run(), False), ("Dynamic resolution", dynamic_run(), True)]
    height = LANE_TOP + LANE_H * len(lanes) + 20
    title = "Dynamic resolution, frame by frame"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{title}">',
        f"<title>{title}</title>",
        f"<style>{STYLE}{CHART_STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{background}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="14"/>')
    parts.append(text(20, 30, title, "title", "start"))
    description = (
        "An illustration, not a measurement: the GPU time of each frame at 60 Hz as the load rises through a busy stretch, then jumps",
        f"at a camera cut. Dynamic resolution lowers the resolution from GPU times it learns {MEASURE_DELAY} frames late, so it follows a slow rise but",
        "not a sudden one. A red frame is over the 16.7 ms budget and misses its refresh.",
    )
    for i, line in enumerate(description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))
    frame_w = (PLOT_X1 - PLOT_X0) / FRAMES
    for lane, (name, run, show_scale) in enumerate(lanes):
        top = LANE_TOP + lane * LANE_H
        missed = sum(time > REFRESH_MS for time in run.gpu)
        parts.append(text(20, top + 8, name, "lane", "start"))
        note = f"{missed} of {FRAMES} frames miss their refresh" + (" · the blue line is the resolution, per axis" if show_scale else "")
        parts.append(text(20 + len(name) * 8.4 + 14, top + 8, note, "vsync-n", "start"))
        plot_top = top + 24
        plot_bottom = plot_top + PLOT_H

        def y_of(value: float, plot_bottom: float = plot_bottom) -> float:
            return plot_bottom - value / TOP_MS * PLOT_H

        for tick in (10, 20, 30):
            y = y_of(tick)
            parts.append(f'<line class="grid" x1="{PLOT_X0}" y1="{y:.1f}" x2="{PLOT_X1}" y2="{y:.1f}"/>')
            parts.append(text(PLOT_X0 - 10, y + 4, f"{tick} ms", "vsync-n", "end"))
        parts.append(text(20, plot_top + PLOT_H / 2 + 4, "GPU TIME", "label", "start"))
        for frame, time in enumerate(run.gpu):
            x = PLOT_X0 + frame * frame_w
            y = y_of(min(time, TOP_MS))
            cls = "miss" if time > REFRESH_MS else "ok"
            parts.append(f'<rect class="{cls}" x="{x + 0.5:.1f}" y="{y:.1f}" width="{frame_w - 1:.1f}" height="{plot_bottom - y:.1f}"/>')
        budget_y = y_of(REFRESH_MS)
        parts.append(f'<line class="budget" x1="{PLOT_X0}" y1="{budget_y:.1f}" x2="{PLOT_X1}" y2="{budget_y:.1f}"/>')
        parts.append(text(PLOT_X1 + 8, budget_y + 4, f"budget {ms(REFRESH_MS)} ms", "budget-text", "start"))
        if show_scale:
            # The resolution scale on its own axis, 50 % at the bottom of the plot and 100 % at the top
            def scale_y(value: float, plot_top: float = plot_top) -> float:
                return plot_top + (MAX_SCALE - value) / (MAX_SCALE - MIN_SCALE) * PLOT_H

            points = " ".join(f"{PLOT_X0 + (frame + 0.5) * frame_w:.1f},{scale_y(value):.1f}" for frame, value in enumerate(run.scale))
            parts.append(f'<polyline class="scale" points="{points}"/>')
            parts.append(text(PLOT_X1 + 8, scale_y(MAX_SCALE) + 4, "100 %", "scale-text", "start"))
            parts.append(text(PLOT_X1 + 8, scale_y(MIN_SCALE) + 4, "50 %", "scale-text", "start"))
        parts.append(text(PLOT_X0, plot_bottom + 18, "0 s", "vsync-n"))
        parts.append(text((PLOT_X0 + PLOT_X1) / 2, plot_bottom + 18, "1 s", "vsync-n"))
        parts.append(text(PLOT_X1, plot_bottom + 18, "2 s", "vsync-n"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Arguments(argparse.Namespace):
    output_dir: Path
    png: bool
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the dynamic resolution chart (SVG, optionally PNG).")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the file goes (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x, through a headless Edge or Chrome")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, such as #ffffff, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "chart-dynamic-resolution.svg"
    _ = path.write_text(render(args.background), encoding="utf-8", newline="\n")
    print(path)
    if args.png:
        png = path.with_suffix(".png")
        save_png(find_browser(), path, png, args.background)
        print(png)


if __name__ == "__main__":
    main()
