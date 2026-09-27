#!/usr/bin/env python3
"""Generate the render pipeline diagram (render-pipeline.svg): how a frame with a lower render resolution is made, in three steps
from real frames of the render scale video's scene (generate_render_scale_video.py). 1: the 3D scene rendered at the render
resolution, drawn at its true, smaller size; 2: scaled up to the output resolution; 3: the UI drawn on top at the output
resolution. Each step shows the same part of the frame, around a cube and the UI panel, in the style of the timing diagrams.

The diagram is 1000 wide, the width the web page shows diagrams at, so the crops are shown close to their real pixels.

Run from the repository's .venv:
  python tools/frame_pacing_video/generate_render_pipeline.py [--output-dir DIR] [--scale S]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import base64
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "timing_diagrams"))

from generate_diagrams import DEFAULT_OUTPUT_DIR, STYLE, text  # noqa: E402
from generate_render_scale_video import OUTPUT_H, OUTPUT_W, UI_LEFT, Renderer, draw_game_ui  # noqa: E402

FRAME = 60  # of a 240-frame clip: the cube turned a little
CLIP_FRAMES = 240
CROP = (8, 150, 356, 382)  # the part of the output shown: a cube and the UI panel, in output pixels

WIDTH = 1000
PANEL_W = 280
ARROW_W = (WIDTH - 40 - 3 * PANEL_W) / 2
PANEL_H = round(PANEL_W * (CROP[3] - CROP[1]) / (CROP[2] - CROP[0]))
PANELS_Y = 150
HEIGHT = PANELS_Y + PANEL_H + 30

DIAGRAM_STYLE = """
  .outline { fill: none; stroke: #8b949e; stroke-width: 1.5; stroke-dasharray: 6 4; }
  .arrow { stroke: #c9d1d9; stroke-width: 2; fill: none; }
  .arrow-head { fill: #c9d1d9; }
  .step { font-size: 13px; font-weight: 600; fill: #e6edf3; }
  .step-sub { font-size: 12px; fill: #8b949e; }
"""


def stages(scale: float) -> tuple[Image.Image, Image.Image, Image.Image]:
    """The crop at each step: rendered at `scale` (its true, smaller size), scaled up, and with the UI drawn at full resolution."""
    renderer = Renderer()
    width, height = round(OUTPUT_W * scale), round(OUTPUT_H * scale)
    rendered = renderer.render(width, height, FRAME, CLIP_FRAMES, True)
    scaled_up = rendered.resize((OUTPUT_W, OUTPUT_H), Image.Resampling.BILINEAR)  # pyright: ignore[reportUnknownMemberType]
    finished = scaled_up.copy()
    draw_game_ui(finished, UI_LEFT, 1.0)
    ratio = width / OUTPUT_W
    small_crop = (round(CROP[0] * ratio), round(CROP[1] * ratio), round(CROP[2] * ratio), round(CROP[3] * ratio))
    return rendered.crop(small_crop), scaled_up.crop(CROP), finished.crop(CROP)


def png_data(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def render(scale: float, background: str | None) -> str:
    title = "From render resolution to the finished frame"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{title}">',
        f"<title>{title}</title>",
        f"<style>{STYLE}{DIAGRAM_STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{background}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14"/>')
    parts.append(text(20, 30, title, "title", "start"))
    percent = round(scale * 100)
    description = (
        f"The same part of one frame at each step, rendered at {percent} % per axis. The 3D scene is rendered small and scaled up, so it",
        "softens; the UI is drawn after that, at the output resolution, so its text stays sharp.",
    )
    for i, line in enumerate(description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))
    steps = (
        ("1 · Render the 3D scene", f"at {percent} % per axis: {round(scale * scale * 100)} % of the pixels"),
        ("2 · Scale it up", "to the output resolution"),
        ("3 · Draw the UI", "at the output resolution"),
    )
    images = stages(scale)
    for index, ((step, sub), image) in enumerate(zip(steps, images, strict=True)):
        x = 20 + index * (PANEL_W + ARROW_W)
        parts.append(text(x, PANELS_Y - 30, step, "step", "start"))
        parts.append(text(x, PANELS_Y - 12, sub, "step-sub", "start"))
        if index == 0:
            # Its true size: the rendered crop is `scale` of the panel, inside the outline of the output's crop
            parts.append(f'<rect class="outline" x="{x}" y="{PANELS_Y}" width="{PANEL_W}" height="{PANEL_H}"/>')
            w, h = PANEL_W * scale, PANEL_H * scale
        else:
            w, h = PANEL_W, PANEL_H
        parts.append(f'<image x="{x}" y="{PANELS_Y}" width="{w:.1f}" height="{h:.1f}" href="data:image/png;base64,{png_data(image)}"/>')
        if index < 2:
            y = PANELS_Y + PANEL_H / 2
            x0, x1 = x + PANEL_W + 10, x + PANEL_W + ARROW_W - 10
            parts.append(f'<line class="arrow" x1="{x0:.1f}" y1="{y}" x2="{x1 - 10:.1f}" y2="{y}"/>')
            parts.append(f'<polygon class="arrow-head" points="{x1:.1f},{y} {x1 - 12:.1f},{y - 6} {x1 - 12:.1f},{y + 6}"/>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Arguments(argparse.Namespace):
    output_dir: Path
    scale: float
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the render pipeline diagram (SVG with the frames embedded).")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the file goes (default: doc/images)")
    _ = parser.add_argument("--scale", type=float, default=0.5, help="the render scale per axis (default: 0.5)")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "render-pipeline.svg"
    _ = path.write_text(render(args.scale, args.background), encoding="utf-8", newline="\n")
    print(path)


if __name__ == "__main__":
    main()
