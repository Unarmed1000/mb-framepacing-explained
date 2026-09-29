#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate the render scale diagram (render-scale.svg): what a lower render resolution renders and what the display gets, as
boxes drawn to scale. On the left the render resolution at 100, 75 and 50 % of the output per axis, inside the output size; on the
right the fixed output the 3D scene is scaled up to, where the UI is drawn at full resolution. In the style of the timing
diagrams.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_render_scale.py [--output-dir DIR] [--png] [--background COLOUR]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
from pathlib import Path

from generate_diagrams import DEFAULT_OUTPUT_DIR, STYLE, find_browser, save_png, text

OUTPUT = (3840, 2160)  # a 4K display
SCALES = (1.0, 0.75, 0.5)  # the render resolution, per axis

WIDTH = 1180
BOX_W, BOX_H = 400, 225  # the output size, drawn
LEFT_X, RIGHT_X = 110, WIDTH - 110 - BOX_W
BOXES_Y = 150
HEIGHT = BOXES_Y + BOX_H + 70

DIAGRAM_STYLE = """
  .outline { fill: none; stroke: #8b949e; stroke-width: 1.5; stroke-dasharray: 6 4; }
  .scale-0 { fill: #58a6ff; fill-opacity: 0.12; stroke: #58a6ff; stroke-opacity: 0.5; stroke-width: 1; }
  .scale-1 { fill: #58a6ff; fill-opacity: 0.22; stroke: #58a6ff; stroke-opacity: 0.7; stroke-width: 1; }
  .scale-2 { fill: #58a6ff; fill-opacity: 0.38; stroke: #58a6ff; stroke-width: 1.5; }
  .output { fill: #2ea043; fill-opacity: 0.16; stroke: #2ea043; stroke-width: 1.5; }
  .ui { fill: none; stroke: #d29922; stroke-width: 1.5; }
  .arrow { stroke: #c9d1d9; stroke-width: 2; fill: none; }
  .arrow-head { fill: #c9d1d9; }
  .box-text { font-size: 12px; fill: #e6edf3; }
  .box-sub { font-size: 11px; fill: #8b949e; }
  .ui-text { font-size: 11px; fill: #d29922; }
"""


def render(background: str | None) -> str:
    title = "Render resolution and output resolution"
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
        "Drawn to scale, for a 4K display. The 3D scene renders at a lower width and height and is scaled up to the fixed output size;",
        "the UI is drawn on top at full resolution, so text stays sharp. 75 % per axis is 56 % of the pixels, 50 % a quarter.",
    )
    for i, line in enumerate(description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))

    # The render target: the output size as an outline, the rendered area in its top left corner at each scale
    parts.append(text(LEFT_X, BOXES_Y - 14, "RENDER RESOLUTION", "label", "start"))
    parts.append(f'<rect class="outline" x="{LEFT_X}" y="{BOXES_Y}" width="{BOX_W}" height="{BOX_H}"/>')
    for index, scale in enumerate(SCALES):
        w, h = BOX_W * scale, BOX_H * scale
        parts.append(f'<rect class="scale-{index}" x="{LEFT_X}" y="{BOXES_Y}" width="{w:.1f}" height="{h:.1f}"/>')
    for scale in SCALES:
        w, h = BOX_W * scale, BOX_H * scale
        width, height = round(OUTPUT[0] * scale), round(OUTPUT[1] * scale)
        pixels = "all the pixels" if scale == 1.0 else f"{round(scale * scale * 100)} % of the pixels"
        parts.append(text(LEFT_X + w - 8, BOXES_Y + h - 22, f"{round(scale * 100)} %: {width} × {height}", "box-text", "end"))
        parts.append(text(LEFT_X + w - 8, BOXES_Y + h - 8, pixels, "box-sub", "end"))

    # The arrow: scale up
    y = BOXES_Y + BOX_H / 2
    x0, x1 = LEFT_X + BOX_W + 24, RIGHT_X - 24
    parts.append(f'<line class="arrow" x1="{x0}" y1="{y}" x2="{x1 - 10}" y2="{y}"/>')
    parts.append(f'<polygon class="arrow-head" points="{x1},{y} {x1 - 12},{y - 6} {x1 - 12},{y + 6}"/>')
    parts.append(text((x0 + x1) / 2, y - 12, "scale up", "axis"))

    # The output: fixed, with the UI drawn on top at full resolution
    parts.append(text(RIGHT_X, BOXES_Y - 14, "OUTPUT: FIXED", "label", "start"))
    parts.append(f'<rect class="output" x="{RIGHT_X}" y="{BOXES_Y}" width="{BOX_W}" height="{BOX_H}"/>')
    parts.append(text(RIGHT_X + BOX_W / 2, BOXES_Y + BOX_H / 2 - 4, f"{OUTPUT[0]} × {OUTPUT[1]}", "box-text"))
    parts.append(text(RIGHT_X + BOX_W / 2, BOXES_Y + BOX_H / 2 + 12, "the 3D scene, scaled up", "box-sub"))
    ui_x, ui_y, ui_w, ui_h = RIGHT_X + 16, BOXES_Y + BOX_H - 46, BOX_W - 32, 30
    parts.append(f'<rect class="ui" x="{ui_x}" y="{ui_y}" width="{ui_w}" height="{ui_h}" rx="4"/>')
    parts.append(text(ui_x + ui_w / 2, ui_y + ui_h / 2 + 4, "UI and text, drawn at 3840 × 2160", "ui-text"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Arguments(argparse.Namespace):
    output_dir: Path
    png: bool
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the render scale diagram (SVG, optionally PNG).")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the file goes (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x, through a headless Edge or Chrome")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, such as #ffffff, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "render-scale.svg"
    _ = path.write_text(render(args.background), encoding="utf-8", newline="\n")
    print(path)
    if args.png:
        png = path.with_suffix(".png")
        save_png(find_browser(), path, png, args.background)
        print(png)


if __name__ == "__main__":
    main()
