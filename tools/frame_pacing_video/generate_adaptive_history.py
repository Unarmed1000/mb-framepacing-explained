#!/usr/bin/env python3
"""Generate the adaptive rate history video: the moving box of a game adapting its rate like Swappy through a busy stretch, and
under it the history the rule keeps (the frames of the last 2 s) as it sees it at each moment, and the target pace it sets from
it. The box is the bottom half of the adapt the rate video's clip (60-busy-full-rate against 60-busy-swappy), made by
generate_videos.py; the history comes from the same simulation (adaptive_rate.py), frame for frame.

The window is drawn as one filled strip, each frame as high as its render time and as wide as it stays on screen, newest on the
right, against a refresh and two; a missed frame is red. The fill is dim with a bright top edge, and there are no gaps between the
frames, so the strip does not flash as it scrolls (WCAG 2.3.1). Next to it the two numbers the rule decides by (the share of the window that missed, the average render time plus
1 ms) against the lines they have to cross, and the target pace. After a change the rule starts a new window: the strip empties and
fills again, and until it holds 2 s the rule decides nothing. At each change a banner says what it decided.

Run from the repository's .venv:
  python tools/frame_pacing_video/generate_adaptive_history.py [--output FILE] [--ffmpeg PATH]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "timing_diagrams"))

from adaptive_rate import BUSY, DROP_THRESHOLD, FRAME_MARGIN_MS, WINDOW_S, Record, with_lead  # noqa: E402
from generate_videos import find_ffmpeg  # noqa: E402

WIDTH, HEIGHT = 1280, 384
FPS = 60
REFRESHES = 480  # 8 s, as the video
REFRESH_MS = 1000 / FPS
WINDOW_REFRESHES = round(WINDOW_S * FPS)
BANNER_REFRESHES = 75  # how long a decision's banner stays
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "out" / "adaptive-rate" / "adaptive-history.mp4"
VIDEO_TOOL = Path(__file__).resolve().parent / "generate_videos.py"
PAIR = ("60-busy-full-rate", "60-busy-swappy")
# The clip's bottom half, as the page shows it (live.ts halfRows): below the divider and a row of margin
BOX_HEIGHT = 384
BOX_ROWS = (194, 384)

BACKGROUND = (22, 26, 31)
CARD = (31, 36, 43)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
FAINT = (110, 118, 129)
GREEN = (46, 160, 67)
RED = (229, 83, 75)
# The history's fill: dim, less than 0.1 in relative luminance above the card, so the scrolling shape does not flash (WCAG 2.3.1);
# its top edge in the full colour
GREEN_FILL = (40, 100, 55)
RED_FILL = (120, 50, 48)
EDGE = 2
AMBER = (210, 153, 34)
BLUE = (88, 166, 255)

# The strip of the window's frames
STRIP = (40, 70, 800, 300)  # left, top, right, bottom
STRIP_MS = 36.0
# The numbers and the pace, to the right of it
PANEL_X = 840


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def window_at(frames: list[Record], refresh: int) -> tuple[list[Record], Record | None]:
    """The frames in the rule's window at `refresh` (the last 2 s, since its last change, as Swappy keeps them) and the latest
    frame shown by then."""
    shown = [f for f in frames if f.shown <= refresh]
    if not shown:
        return [], None
    latest = shown[-1]
    # Swappy's FrameDurations: emptied after a change, then the oldest frame dropped only while the next one is also older than
    # 2 s, so one frame a little older than that stays
    changes = [f.shown for f in shown if f.change is not None]
    window = [f for f in shown if not changes or f.shown > changes[-1]]
    while len(window) >= 2 and (refresh + REFRESHES) / float(FPS) - (window[1].shown + REFRESHES) / float(FPS) > WINDOW_S:
        _ = window.pop(0)
    return window, latest


def draw_frame(frames: list[Record], refresh: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    window, latest = window_at(frames, refresh)
    left, top, right, bottom = STRIP

    # The strip: the window's frames by when they were shown, the newest at the right edge
    draw.rounded_rectangle([left - 16, top - 44, right + 16, bottom + 24], radius=12, fill=CARD)
    draw.text((left, top - 36), f"THE HISTORY: THE FRAMES OF THE LAST {WINDOW_S:g} S", fill=MUTED, font=font(13))

    def y_of(ms: float) -> float:
        return bottom - min(ms, STRIP_MS) / STRIP_MS * (bottom - top)

    def x_of(shown: int) -> float:
        return right - (refresh - shown) / WINDOW_REFRESHES * (right - left)

    lines = ((REFRESH_MS, "one refresh"), (2 * REFRESH_MS, "two refreshes"))
    # One filled shape, no gaps: every frame from its own refresh to the next frame's, dim, with a bright top edge. Separate bright
    # bars with gaps between them make a striped pattern that flashes as it scrolls
    half = (right - left) / WINDOW_REFRESHES / 2
    followers: list[Record | None] = [*window[1:], None] if window else []
    for frame, following in zip(window, followers, strict=True):
        start = max(left, x_of(frame.shown) - half)
        end = min(right, (x_of(following.shown) if following else x_of(refresh) + half) - half)
        if end > start:
            y = y_of(frame.render_ms)
            draw.rectangle([start, y, end, bottom], fill=RED_FILL if frame.missed else GREEN_FILL)
            draw.rectangle([start, y, end, y + EDGE - 1], fill=RED if frame.missed else GREEN)
    # The refresh lines over the history, so they show through the filled shape
    for ms, _ in lines:
        y = y_of(ms)
        for x in range(left, right, 12):
            draw.line([(x, y), (min(x + 6, right), y)], fill=AMBER, width=1)
    draw.line([(left, bottom), (right, bottom)], fill=FAINT, width=1)
    # The lines' names over the strip, on a patch of the card so the strip does not run through them
    for ms, label in lines:
        y = y_of(ms)
        box = draw.textbbox((left + 4, y - 16), label, font=font(12))
        draw.rectangle([box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2], fill=CARD)
        draw.text((left + 4, y - 16), label, fill=AMBER, font=font(12))
    draw.text((left, bottom + 4), f"{WINDOW_S:g} s ago", fill=FAINT, font=font(12))
    newest = draw.textlength("now", font=font(12))
    draw.text((right - newest, bottom + 4), "now", fill=FAINT, font=font(12))
    filling = latest is None or latest.missed_percent is None
    if filling:
        note = f"a new window: the rule decides nothing until it holds {WINDOW_S:g} s"
        width = draw.textlength(note, font=font(14))
        draw.text(((left + right - width) / 2, top + 64), note, fill=MUTED, font=font(14))

    # What the rule sees, its two decisions as checklists (each condition met or not), and the pace it sets
    x = PANEL_X
    draw.rounded_rectangle([x - 16, top - 44, WIDTH - 24, bottom + 24], radius=12, fill=CARD)
    missed = None if latest is None else latest.missed_percent
    average = None if latest is None or latest.average_ms is None else latest.average_ms + FRAME_MARGIN_MS
    interval = 1 if latest is None else next((f for f in frames if f.shown > latest.shown), latest).interval
    span = (window[-1].shown - window[0].shown) / FPS if len(window) >= 2 else 0.0
    holds = missed is not None
    draw.text((x, top - 36), "WHAT THE RULE SEES", fill=MUTED, font=font(13))
    draw.text((x, top - 14), "window", fill=MUTED, font=font(14))
    draw.text((x + 70, top - 16), f"{min(span, WINDOW_S):.1f} s of {WINDOW_S:g} s", fill=TEXT if holds else AMBER, font=font(18))
    draw.text((x, top + 10), "missed", fill=MUTED, font=font(14))
    draw.text((x + 70, top + 8), "…" if missed is None else f"{missed} %", fill=TEXT, font=font(18))
    draw.text((x + 180, top + 10), "average + 1 ms", fill=MUTED, font=font(14))
    draw.text((x + 300, top + 8), "…" if average is None else f"{average:.1f} ms", fill=TEXT, font=font(18))

    def checklist(y: float, heading: str, active: bool, conditions: list[tuple[str, bool]]) -> None:
        draw.text((x, y), heading, fill=MUTED if active else FAINT, font=font(13))
        for row, (condition, met) in enumerate(conditions):
            cy = y + 22 + row * 19
            box = [x, cy + 1, x + 13, cy + 14]
            if met and active:
                draw.rounded_rectangle(box, radius=3, fill=GREEN)
                draw.line([(x + 3, cy + 8), (x + 6, cy + 11), (x + 11, cy + 4)], fill=CARD, width=2)
            elif met:
                draw.rounded_rectangle(box, radius=3, outline=GREEN, width=1)
            else:
                draw.rounded_rectangle(box, radius=3, outline=FAINT, width=1)
            draw.text((x + 22, cy), condition, fill=(TEXT if met else MUTED) if active else FAINT, font=font(14))

    checklist(
        top + 44,
        "DROP TO HALF RATE (at full rate) when",
        interval == 1,
        [(f"the window holds {WINDOW_S:g} s", holds), (f"more than {DROP_THRESHOLD} % missed", missed is not None and missed > DROP_THRESHOLD)],
    )
    checklist(
        top + 110,
        "BACK TO FULL RATE (at half rate) when",
        interval > 1,
        [
            (f"the window holds {WINDOW_S:g} s", holds),
            ("none missed", missed == 0),
            (f"average + 1 ms under {REFRESH_MS - FRAME_MARGIN_MS:.1f} ms", average is not None and average < REFRESH_MS - FRAME_MARGIN_MS),
        ],
    )
    draw.text((x, top + 196), "TARGET PACE", fill=MUTED, font=font(13))
    pace = "every refresh: 60 fps" if interval == 1 else f"every {interval} refreshes: {60 // interval} fps"
    draw.text((x, top + 214), pace, fill=BLUE, font=font(22))

    draw.text((24, 14), "THE BOX ABOVE: A GAME ADAPTING ITS RATE LIKE SWAPPY", fill=MUTED, font=font(13))
    # A banner at each decision
    for frame in frames:
        if frame.change is not None and 0 <= refresh - frame.shown < BANNER_REFRESHES:
            text = f"More than {DROP_THRESHOLD} % missed: drop to half rate" if frame.change == "slower" else "None missed, the average fits: back to full rate"
            width = draw.textlength(text, font=font(20))
            box = [(WIDTH - width) / 2 - 18, 6, (WIDTH + width) / 2 + 18, 40]
            draw.rounded_rectangle(box, radius=8, fill=BLUE if frame.change == "faster" else AMBER)
            draw.text(((WIDTH - width) / 2, 12), text, fill=BACKGROUND, font=font(20))

    # The clip's timeline, with the busy stretch
    line_y, t0, t1 = HEIGHT - 26, 40, WIDTH - 40
    busy0, busy1 = t0 + float(BUSY[0]) * (t1 - t0), t0 + float(BUSY[1]) * (t1 - t0)
    draw.rectangle([busy0, line_y - 5, busy1, line_y + 5], fill=(70, 60, 40))
    draw.text((busy0 + 6, line_y - 22), "busy stretch", fill=AMBER, font=font(12))
    draw.line([(t0, line_y), (t1, line_y)], fill=FAINT, width=2)
    at = t0 + refresh / REFRESHES * (t1 - t0)
    draw.ellipse([at - 6, line_y - 6, at + 6, line_y + 6], fill=BLUE)
    draw.text((t1 + 6, line_y - 8), f"{refresh / FPS:.1f} s", fill=MUTED, font=font(12))
    return image


class Arguments(argparse.Namespace):
    output: Path | None
    ffmpeg: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the adaptive rate history video (H.264, for the web page).")
    _ = parser.add_argument("--output", type=Path, default=None, help=f"the video file (default: {DEFAULT_OUTPUT})")
    _ = parser.add_argument("--ffmpeg", default=None, help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    args = parser.parse_args(namespace=Arguments())
    ffmpeg = find_ffmpeg(args.ffmpeg).path
    output = args.output or DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    # The box: the pair clip, lossless, in a folder of its own that goes away after; its bottom half goes on top of the history
    temporary = tempfile.TemporaryDirectory(prefix="adaptive-history-")
    box_dir = Path(temporary.name)
    _ = subprocess.run(
        [sys.executable, str(VIDEO_TOOL), "--speed", "fast", "--height", str(BOX_HEIGHT), "--box-size", "48", "--output-dir", str(box_dir),
         "--pairs", ":".join(PAIR), "--ffmpeg", str(ffmpeg)],
        check=True, capture_output=True,
    )  # fmt: skip
    box = box_dir / "box" / "fast" / f"fast_top-{PAIR[0]}_bottom-{PAIR[1]}.mp4"
    # The pass before the clip in front: the window at the start of the clip holds its frames
    frames = with_lead("swappy", REFRESHES, Fraction(FPS))
    video = [draw_frame(frames, refresh).tobytes() for refresh in range(REFRESHES)]
    rows = BOX_ROWS[1] - BOX_ROWS[0]
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(box),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-filter_complex", f"[0:v]crop={WIDTH}:{rows}:0:{BOX_ROWS[0]},format=rgb24[box];[box][1:v]vstack=inputs=2",
        "-frames:v", str(REFRESHES),
        "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]  # fmt: skip
    _ = subprocess.run(command, input=b"".join(video), check=True)
    temporary.cleanup()
    print(f"{output}: {len(video)} frames, {len(video) / FPS:g} s")


if __name__ == "__main__":
    main()
