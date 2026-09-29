#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate the comparisons of averages of the slides, in the style of the timing diagrams: modes with the same average frame rate, at
the display's own rate, their display time steps against the average and their refresh strips (chart-average-half-rate.svg: 30 fps
evenly and badly paced).

The data comes from the frame pacing videos' own simulation (tools/frame_pacing_video/frame_timing.py), so each lane shows exactly
the frames of the video of that mode. The example report cards of doc/charts.md are mb-framepacing's, measured from the clips:
generate_measured_charts.py.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_charts.py [--output-dir DIR] [--png] [--background COLOUR]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frame_pacing_video"))

from frame_timing import TimingParameters, parse_mode, simulate  # noqa: E402
from generate_diagrams import DEFAULT_OUTPUT_DIR, STYLE, find_browser, ms, save_png, text  # noqa: E402

# The video clips: 8 s at 60 Hz
CLIP_REFRESHES = 480

WIDTH = 1180
PLOT_X0 = 110
PLOT_X1 = WIDTH - 40

# mb-framepacing's report card keeps this sheet verbatim (SvgMarkup.ChartStyle): change them together
CHART_STYLE = """
  .tile { fill: #ffffff; fill-opacity: 0.05; stroke: #ffffff; stroke-opacity: 0.12; stroke-width: 1; }
  .tile-value { font-size: 20px; font-weight: 600; }
  .grid { stroke: #ffffff; stroke-opacity: 0.1; stroke-width: 1; }
  .zero-line { stroke: #ffffff; stroke-opacity: 0.45; stroke-width: 1; }
  .bar { fill: #e5534b; }
  .display-line { stroke: #2ea043; stroke-width: 2; fill: none; }
  .step-line { stroke: #58a6ff; stroke-width: 1.2; fill: none; stroke-linejoin: round; }
  .strip-a { fill: #6e7681; }
  .strip-b { fill: #adbac7; }
  .average-line { stroke: #d29922; stroke-width: 1.5; stroke-dasharray: 6 4; }
  .average-text { fill: #d29922; font-size: 12px; }
"""


@dataclass(frozen=True)
class FrameData:
    """Per frame, in ms: the display time step (how long the previous frame was on screen), the animation time step and the error."""

    display: list[float]
    step: list[float]
    error: list[float]
    flips: tuple[int, ...]
    refresh_ms: float


def frame_data(mode_name: str) -> FrameData:
    parameters = TimingParameters()
    frames = simulate(parse_mode(mode_name), parameters, CLIP_REFRESHES)
    refresh = 1 / parameters.fps
    count = len(frames.flips)
    duration = Fraction(CLIP_REFRESHES) * refresh
    display: list[float] = []
    step: list[float] = []
    for index in range(count):
        # The first frame follows the last one of the previous loop, as in the videos' manifests
        previous_flip = frames.flips[index - 1] - (CLIP_REFRESHES if index == 0 else 0)
        previous_animation = frames.animation[index - 1] - (duration if index == 0 else 0)
        display.append(float((frames.flips[index] - previous_flip) * refresh) * 1000)
        step.append(float(frames.animation[index] - previous_animation) * 1000)
    error = [s - d for s, d in zip(step, display, strict=True)]
    return FrameData(display, step, error, frames.flips, float(refresh) * 1000)


@dataclass(frozen=True)
class AverageComparison:
    """Modes with the same average frame rate side by side, at the display's own rate: their display time step per frame over the
    first second against the average, and their refresh strips, so the same average and the different pacing show at once."""

    name: str
    title: str
    description: tuple[str, ...]
    lanes: tuple[tuple[str, str], ...]  # (lane title, video mode)


AVERAGE_COMPARISONS = (
    AverageComparison(
        "average-half-rate",
        "Same 30 fps on average, different motion",
        (
            "A 60 Hz display, the first second of each: both show 30 frames a second, 33.3 ms per frame on average. Only how long each",
            "frame stays on screen differs: two refreshes every time, or three and then one. The average frame rate cannot tell them apart.",
        ),
        (("Evenly paced", "60-diagram-half-rate-even"), ("Bad frame pacing", "60-diagram-half-rate-bad-pacing")),
    ),
)

AVG_LANE_TOP = 108
AVG_PLOT_H = 96
AVG_STRIP_H = 22
AVG_LANE_H = 24 + AVG_PLOT_H + 40 + AVG_STRIP_H + 44


def render_average_comparison(comparison: AverageComparison, background: str | None) -> str:
    lanes = [(title, frame_data(mode)) for title, mode in comparison.lanes]
    height = AVG_LANE_TOP + AVG_LANE_H * len(lanes) + 10
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(comparison.title)}">',
        f"<title>{escape(comparison.title)}</title>",
        f"<style>{STYLE}{CHART_STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{escape(background)}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="14"/>')
    parts.append(text(20, 30, comparison.title, "title", "start"))
    for i, line in enumerate(comparison.description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))
    top_ms = max(max(data.display) for _, data in lanes) * 1.15
    for lane, (title, data) in enumerate(lanes):
        top = AVG_LANE_TOP + lane * AVG_LANE_H
        refreshes = round(1000 / data.refresh_ms)  # one second
        seconds = CLIP_REFRESHES * data.refresh_ms / 1000
        average_rate = len(data.display) / seconds
        average_ms = sum(data.display) / len(data.display)
        values = sorted({round(d, 1) for d in data.display})
        shown = "every frame " + f"{ms(values[0])} ms" if len(values) == 1 else " and ".join(f"{ms(v)}" for v in values) + " ms"
        parts.append(text(20, top, title, "lane", "start"))
        parts.append(text(20 + len(title) * 8.4 + 14, top, f"{average_rate:g} fps on average ({ms(average_ms)} ms) · on screen {shown}", "vsync-n", "start"))
        plot_top = top + 24
        plot_bottom = plot_top + AVG_PLOT_H

        def y_of(value: float, plot_bottom: float = plot_bottom) -> float:
            return plot_bottom - value / top_ms * AVG_PLOT_H

        # The frames of the first second: each frame's display time step, held until the next frame
        in_second = [index for index, flip in enumerate(data.flips) if flip < refreshes]
        cell_w = (PLOT_X1 - PLOT_X0) / refreshes
        tick = data.refresh_ms
        while tick < top_ms:
            y = y_of(tick)
            parts.append(f'<line class="grid" x1="{PLOT_X0}" y1="{y:.1f}" x2="{PLOT_X1}" y2="{y:.1f}"/>')
            parts.append(text(PLOT_X0 - 10, y + 4, f"{ms(round(tick, 1))} ms", "vsync-n", "end"))
            tick += data.refresh_ms
        parts.append(f'<line class="zero-line" x1="{PLOT_X0}" y1="{plot_bottom}" x2="{PLOT_X1}" y2="{plot_bottom}"/>')
        points: list[str] = []
        for index in in_second:
            # A frame's display time step is how long the previous one was on screen: draw it from the previous frame's flip
            end = data.flips[index]
            start = end - round(data.display[index] / data.refresh_ms)
            y = y_of(data.display[index])
            points += [f"{PLOT_X0 + max(0, start) * cell_w:.1f},{y:.1f}", f"{PLOT_X0 + end * cell_w:.1f},{y:.1f}"]
        parts.append(f'<polyline class="display-line" points="{" ".join(points)}"/>')
        average_y = y_of(average_ms)
        parts.append(f'<line class="average-line" x1="{PLOT_X0}" y1="{average_y:.1f}" x2="{PLOT_X1}" y2="{average_y:.1f}"/>')
        parts.append(text(PLOT_X1, average_y - 6, f"average {ms(average_ms)} ms = {average_rate:g} fps", "average-text", "end"))

        # The refresh strip of the same second
        strip_top = plot_bottom + 40
        parts.append(text(20, strip_top + AVG_STRIP_H / 2 + 4, "REFRESHES", "label", "start"))
        flips = set(data.flips)
        shade = 0
        for refresh in range(refreshes):
            if refresh in flips and refresh:
                shade ^= 1
            x = PLOT_X0 + refresh * cell_w
            parts.append(
                f'<rect class="{"strip-a" if shade == 0 else "strip-b"}" x="{x + 0.5:.1f}" y="{strip_top}" width="{cell_w - 1:.1f}" height="{AVG_STRIP_H}" rx="2"/>'
            )
        parts.append(text(PLOT_X0, strip_top + AVG_STRIP_H + 18, "0 s", "vsync-n"))
        parts.append(text(PLOT_X1, strip_top + AVG_STRIP_H + 18, "1 s", "vsync-n"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Arguments(argparse.Namespace):
    output_dir: Path
    png: bool
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the comparisons of averages (SVG, optionally PNG).")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the files go (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x of each, through a headless Edge or Chrome")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, such as #ffffff, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    browser = find_browser() if args.png else None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [(f"chart-{c.name}.svg", render_average_comparison(c, args.background)) for c in AVERAGE_COMPARISONS]
    for name, svg in outputs:
        path = args.output_dir / name
        _ = path.write_text(svg, encoding="utf-8", newline="\n")
        print(path)
        if browser:
            png = path.with_suffix(".png")
            save_png(browser, path, png, args.background)
            print(png)


if __name__ == "__main__":
    main()
