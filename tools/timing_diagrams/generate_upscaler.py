#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate the temporal upscaler diagram (upscaler.svg): roughly how DLSS and FSR 2 and later build a frame at the display
resolution. On the left the inputs, this frame's colour, depth and motion vectors at the render resolution and the last output at
the display resolution; in the middle the upscaler's steps; on the right the output, which becomes the next frame's history. In
the style of the timing diagrams.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_upscaler.py [--output-dir DIR] [--png] [--background COLOUR]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
from pathlib import Path

from generate_diagrams import DEFAULT_OUTPUT_DIR, STYLE, find_browser, save_png, text

WIDTH = 1180
TOP = 150  # the top of the boxes
INPUT_X, INPUT_W, INPUT_H, INPUT_GAP = 40, 230, 44, 12
HISTORY_Y = TOP + 3 * (INPUT_H + INPUT_GAP) + 34
UPSCALER_X, UPSCALER_W = 360, 420
OUTPUT_X, OUTPUT_W = 870, 270
BOTTOM = HISTORY_Y + INPUT_H  # the bottom of the boxes
LOOP_Y = BOTTOM + 36
HEIGHT = LOOP_Y + 40

INPUTS = (
    ("Colour, jittered", "the camera shifted a fraction of a pixel"),
    ("Depth", "how far away each pixel is"),
    ("Motion vectors", "where each pixel was last frame"),
)
STEPS = (
    ("1 · Move the history", ("along the motion vectors, to where it is now",)),
    ("2 · Reject what no longer fits", ("uncovered or changed pixels, using the depth",)),
    ("3 · Blend in this frame's samples", ("each jitter lands in a different place in the pixel,", "so over frames there are more samples than pixels")),
)

DIAGRAM_STYLE = """
  .input { fill: #58a6ff; fill-opacity: 0.22; stroke: #58a6ff; stroke-width: 1.5; }
  .history { fill: #2ea043; fill-opacity: 0.10; stroke: #2ea043; stroke-width: 1.5; stroke-dasharray: 6 4; }
  .upscaler { fill: #8b949e; fill-opacity: 0.10; stroke: #8b949e; stroke-width: 1.5; }
  .output { fill: #2ea043; fill-opacity: 0.16; stroke: #2ea043; stroke-width: 1.5; }
  .arrow { stroke: #c9d1d9; stroke-width: 2; fill: none; }
  .loop { stroke: #2ea043; stroke-width: 2; fill: none; stroke-dasharray: 6 4; }
  .arrow-head { fill: #c9d1d9; }
  .loop-head { fill: #2ea043; }
  .box-text { font-size: 13px; font-weight: 600; fill: #e6edf3; }
  .box-sub { font-size: 11px; fill: #8b949e; }
  .step { font-size: 13px; font-weight: 600; fill: #e6edf3; }
  .step-sub { font-size: 12px; fill: #8b949e; }
  .network { font-size: 12px; fill: #d29922; }
  .loop-text { font-size: 12px; fill: #2ea043; }
"""


def arrow(x0: float, y0: float, x1: float, y1: float, loop: bool = False) -> list[str]:
    """A straight arrow from (x0, y0) to (x1, y1), horizontal or vertical, its head at the end."""
    line, head = ("loop", "loop-head") if loop else ("arrow", "arrow-head")
    if y0 == y1:
        d = 1 if x1 > x0 else -1
        points = f"{x1},{y1} {x1 - 12 * d},{y1 - 6} {x1 - 12 * d},{y1 + 6}"
        end = (x1 - 10 * d, y1)
    else:
        d = 1 if y1 > y0 else -1
        points = f"{x1},{y1} {x1 - 6},{y1 - 12 * d} {x1 + 6},{y1 - 12 * d}"
        end = (x1, y1 - 10 * d)
    return [f'<line class="{line}" x1="{x0}" y1="{y0}" x2="{end[0]}" y2="{end[1]}"/>', f'<polygon class="{head}" points="{points}"/>']


def render(background: str | None) -> str:
    title = "A temporal upscaler, roughly"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{title}">',
        f"<title>{title}</title>",
        f"<style>{STYLE}{DIAGRAM_STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{background}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14"/>')
    parts.append(text(20, 30, title, "title", "start"))
    description = (
        "DLSS and FSR 2 and later: every frame renders fewer pixels, and the upscaler adds them to the frames before it. A plain scale up",
        "(and FSR 1) only has the current frame; a temporal upscaler has the history, so it can rebuild detail the current frame lacks.",
    )
    for i, line in enumerate(description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))

    # The inputs: this frame at the render resolution, and the history at the display resolution
    parts.append(text(INPUT_X, TOP - 14, "THIS FRAME, RENDER RESOLUTION", "label", "start"))
    for index, (name, sub) in enumerate(INPUTS):
        y = TOP + index * (INPUT_H + INPUT_GAP)
        parts.append(f'<rect class="input" x="{INPUT_X}" y="{y}" width="{INPUT_W}" height="{INPUT_H}" rx="4"/>')
        parts.append(text(INPUT_X + 12, y + 19, name, "box-text", "start"))
        parts.append(text(INPUT_X + 12, y + 35, sub, "box-sub", "start"))
        parts += arrow(INPUT_X + INPUT_W + 8, y + INPUT_H / 2, UPSCALER_X - 8, y + INPUT_H / 2)
    parts.append(text(INPUT_X, HISTORY_Y - 14, "LAST OUTPUT, DISPLAY RESOLUTION", "label", "start"))
    parts.append(f'<rect class="history" x="{INPUT_X}" y="{HISTORY_Y}" width="{INPUT_W}" height="{INPUT_H}" rx="4"/>')
    parts.append(text(INPUT_X + 12, HISTORY_Y + 19, "History", "box-text", "start"))
    parts.append(text(INPUT_X + 12, HISTORY_Y + 35, "the frames before, built up", "box-sub", "start"))
    parts += arrow(INPUT_X + INPUT_W + 8, HISTORY_Y + INPUT_H / 2, UPSCALER_X - 8, HISTORY_Y + INPUT_H / 2)

    # The upscaler's steps
    parts.append(text(UPSCALER_X, TOP - 14, "THE UPSCALER", "label", "start"))
    parts.append(f'<rect class="upscaler" x="{UPSCALER_X}" y="{TOP}" width="{UPSCALER_W}" height="{BOTTOM - TOP}" rx="6"/>')
    y = TOP + 26
    for step, lines in STEPS:
        parts.append(text(UPSCALER_X + 16, y, step, "step", "start"))
        for line in lines:
            y += 17
            parts.append(text(UPSCALER_X + 16, y, line, "step-sub", "start"))
        y += 28
    parts.append(text(UPSCALER_X + 16, BOTTOM - 36, "DLSS and FSR 4: a trained neural network does 2 and 3.", "network", "start"))
    parts.append(text(UPSCALER_X + 16, BOTTOM - 18, "FSR 2 and 3: hand-written (analytical) rules.", "network", "start"))

    # The output, which is the next frame's history
    middle = (TOP + BOTTOM) / 2
    parts += arrow(UPSCALER_X + UPSCALER_W + 8, middle, OUTPUT_X - 8, middle)
    parts.append(text(OUTPUT_X, TOP - 14, "OUTPUT, DISPLAY RESOLUTION", "label", "start"))
    parts.append(f'<rect class="output" x="{OUTPUT_X}" y="{TOP}" width="{OUTPUT_W}" height="{BOTTOM - TOP}" rx="6"/>')
    parts.append(text(OUTPUT_X + OUTPUT_W / 2, middle - 4, "This frame", "box-text"))
    parts.append(text(OUTPUT_X + OUTPUT_W / 2, middle + 14, "then post-processing and the UI", "box-sub"))
    parts.append(text(OUTPUT_X + OUTPUT_W / 2, middle + 30, "at the display resolution", "box-sub"))

    # The loop: the output becomes the next frame's history
    loop_x0, loop_x1 = OUTPUT_X + OUTPUT_W / 2, INPUT_X + INPUT_W / 2
    parts.append(f'<polyline class="loop" points="{loop_x0},{BOTTOM + 8} {loop_x0},{LOOP_Y} {loop_x1},{LOOP_Y} {loop_x1},{BOTTOM + 18}"/>')
    parts.append(f'<polygon class="loop-head" points="{loop_x1},{BOTTOM + 8} {loop_x1 - 6},{BOTTOM + 20} {loop_x1 + 6},{BOTTOM + 20}"/>')
    parts.append(text((loop_x0 + loop_x1) / 2, LOOP_Y - 8, "kept as the next frame's history", "loop-text"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Arguments(argparse.Namespace):
    output_dir: Path
    png: bool
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the temporal upscaler diagram (SVG, optionally PNG).")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the file goes (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x, through a headless Edge or Chrome")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, such as #ffffff, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "upscaler.svg"
    _ = path.write_text(render(args.background), encoding="utf-8", newline="\n")
    print(path)
    if args.png:
        png = path.with_suffix(".png")
        save_png(find_browser(), path, png, args.background)
        print(png)


if __name__ == "__main__":
    main()
