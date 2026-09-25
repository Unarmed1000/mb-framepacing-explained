#!/usr/bin/env python3
"""Generate the timing diagrams of the docs: SVG timelines of a game loop on a display.

Each diagram shows the two clocks behind animation error. The render row has one box per frame, labelled with the frame's
animation time (the moment of game time it shows) and as wide as its rendering takes; an arrow marks where it is presented. The
display row shows which frame is on screen at each refresh: green when it shows that refresh's moment, light green when it is held
for a refresh as intended (swap interval 2), amber when the previous frame is held because the next one is not ready, red when it
shows another moment. The time of every refresh is written just below it. Under that, for every frame when it first appears, the
animation time step, the display time (how long the previous frame was on screen) and their difference: the animation error as
PresentMon computes it (positive: shown too soon, negative: shown too late).

The loop is double buffered: a frame starts rendering when the previous one appears (the first one somewhere inside a refresh). With vsync it appears at the first refresh
after it is presented and at least its swap interval after the previous one; with VRR the display refreshes as soon as it is
presented, but at most every 100 ms. The display runs at 10 Hz (a refresh every 100 ms), a slowed-down 60 Hz, so the numbers stay
readable. A perfect timer gives each frame the moment it expects to be shown: its start plus its swap interval.

The SVGs are transparent, with everything on a rounded, slightly translucent dark grey card, so they read the same on a white and
on a dark page (--background adds an opaque page colour behind the card, for previews). They are vector graphics, so
GitHub shows them sharp at any size. --png also saves each as a PNG at 2x, through a headless Edge or Chrome (MB_BROWSER, or the
usual install locations and PATH).

Run from the repository's .venv:
  python tools/timing_diagrams/generate_diagrams.py [--output-dir DIR] [--png] [NAME ...]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import functools
import math
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "doc" / "images"
BROWSER_ENVIRONMENT_VARIABLE = "MB_BROWSER"
BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
BROWSER_NAMES = ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser")

# The display: one refresh every PERIOD ms (10 Hz), the first frame shown at 0 ms
PERIOD = 100.0
EPSILON = 1e-9
# How far into its refresh the first frame starts rendering (ms): the loop begins somewhere inside a refresh, not on a vsync
FIRST_START = 20.0

# Layout, in SVG pixels
SCALE = 1.2  # pixels per ms
LEFT = 180  # width of the row label column
RIGHT = 40
VSYNC_Y = 98  # the refresh labels above the lines
RENDER_Y = VSYNC_Y + 14
RENDER_H = 44
ARROW_Y0 = RENDER_Y + RENDER_H + 8
DISPLAY_Y = ARROW_Y0 + 34
DISPLAY_H = 40
AXIS_Y = DISPLAY_Y + DISPLAY_H + 20  # the refresh times, just below the display row
ROWS_Y = AXIS_Y + 36
ROW_STEP = 26
ROW_LABELS = ("Animation time step", "Display time", "Animation error")
LEGEND_Y = ROWS_Y + ROW_STEP * len(ROW_LABELS) + 22
HEIGHT = LEGEND_Y + 70

# Designed for a black or transparent background
STYLE = """
  text { font-family: "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
         font-size: 13px; fill: #e6edf3; font-variant-numeric: tabular-nums; }
  .card { fill: #1f242b; fill-opacity: 0.94; stroke: #8b949e; stroke-opacity: 0.25; stroke-width: 1; }
  .title { font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
  .sub { fill: #8b949e; }
  .label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; fill: #8b949e; }
  .vsync-n { font-size: 11px; fill: #6e7681; letter-spacing: 0.04em; }
  .axis { font-size: 12px; fill: #c9d1d9; }
  .vsync { stroke: #ffffff; stroke-opacity: 0.16; stroke-width: 1; stroke-dasharray: 3 4; }
  .box { fill: #ffffff; fill-opacity: 0.06; stroke: #ffffff; stroke-opacity: 0.22; stroke-width: 1; }
  .frame { font-size: 14px; font-weight: 700; }
  .box-time { fill: #b1bac4; font-size: 12px; }
  .arrow { stroke: #8b949e; stroke-width: 1.2; }
  .arrowhead { fill: #8b949e; }
  .ok { fill: #2ea043; }
  .hold { fill: #2ea043; fill-opacity: 0.45; }
  .again { fill: #d29922; }
  .off { fill: #e5534b; }
  .cell-text { font-size: 14px; font-weight: 700; fill: #ffffff; }
  .dark-text { fill: #1c1f24; }
  .zero { fill: #6e7681; }
  .err { fill: #ff7b72; font-weight: 600; }
  .err-pill { fill: #e5534b; fill-opacity: 0.16; }
  .neutral { fill: #3d444d; }
  .lane { font-size: 15px; font-weight: 600; }
  .same { fill: #7ee787; font-weight: 600; }
"""

LEGEND = {
    "ok": "shows the moment of its refresh",
    "hold": "held as intended (swap interval)",
    "again": "held: the next frame is not ready",
    "off": "shows another moment",
}


@dataclass(frozen=True)
class Frame:
    """A frame of the loop: its name, how long it takes until it is presented (ms), how many refreshes it is meant to stay on
    screen (its swap interval), and how far its timer reading is off (ms)."""

    name: str
    render: float
    interval: int = 1
    timer_error: float = 0.0


@dataclass(frozen=True)
class Diagram:
    name: str
    title: str
    description: tuple[str, ...]
    frames: tuple[Frame, ...]
    # VRR: the display refreshes when a frame is presented (at most every PERIOD ms) instead of at fixed vsyncs
    vrr: bool = False
    # A fixed animation step per frame (ms) instead of the perfect timer, like a game that assumes its target frame rate
    fixed_step: float | None = None


@dataclass(frozen=True)
class Timed:
    """A frame after simulation: when it renders, its animation time, and when it first appears."""

    frame: Frame
    start: float
    end: float
    animation: float
    shown: float


@dataclass(frozen=True)
class Cell:
    """What one refresh shows: from when to when, which frame, and how it is coloured."""

    start: float
    end: float
    timed: Timed
    kind: str
    first: bool


def simulate(diagram: Diagram) -> list[Timed]:
    timed: list[Timed] = []
    previous_shown = -diagram.frames[0].interval * PERIOD
    for index, frame in enumerate(diagram.frames):
        # The loop begins somewhere inside a refresh; every later frame starts at the flip that shows the previous one
        start = previous_shown + (FIRST_START if index == 0 else 0)
        end = start + frame.render
        if diagram.vrr:
            shown = max(end, previous_shown + PERIOD)
        else:
            shown = max(math.ceil(end / PERIOD - EPSILON) * PERIOD, previous_shown + frame.interval * PERIOD)
        if diagram.fixed_step is not None:
            animation = index * diagram.fixed_step
        else:
            animation = previous_shown + frame.interval * PERIOD + frame.timer_error
        timed.append(Timed(frame, start, end, animation, shown))
        previous_shown = shown
    return timed


def cells(diagram: Diagram, timed: list[Timed]) -> list[Cell]:
    last = timed[-1]
    if diagram.vrr:
        bounds = [(t.shown, t) for t in timed]
        ends = [t.shown for t in timed[1:]] + [last.shown + PERIOD]
        spans = [(start, end, t) for (start, t), end in zip(bounds, ends, strict=True)]
    else:
        stop = last.shown + last.frame.interval * PERIOD
        spans: list[tuple[float, float, Timed]] = []
        for k in range(round(stop / PERIOD)):
            at = k * PERIOD
            spans.append((at, at + PERIOD, [t for t in timed if t.shown <= at + EPSILON][-1]))
    result: list[Cell] = []
    previous: Timed | None = None
    for start, end, t in spans:
        first = t is not previous
        if abs(t.animation - start) < EPSILON:
            kind = "ok"
        elif first:
            kind = "off"
        elif start - t.shown < t.frame.interval * PERIOD - EPSILON:
            kind = "hold"
        else:
            kind = "again"
        result.append(Cell(start, end, t, kind, first))
        previous = t
    return result


def ms(value: float, sign: bool = False) -> str:
    text = f"{abs(value):.1f}".removesuffix(".0")
    if abs(value) < EPSILON:
        return "0"
    if value < 0:
        return f"\u2212{text}"
    return f"+{text}" if sign else text


def text(x: float, y: float, content: str, cls: str = "", anchor: str = "middle") -> str:
    class_attr = f' class="{cls}"' if cls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{class_attr}>{escape(content)}</text>'


def render(diagram: Diagram, background: str | None) -> str:
    timed = simulate(diagram)
    refreshes = cells(diagram, timed)
    # The refresh before the first frame appears: the first frame starts rendering inside it
    origin = -diagram.frames[0].interval * PERIOD

    def x_of(t: float) -> float:
        return LEFT + (t - origin) * SCALE

    width = x_of(refreshes[-1].end) + RIGHT
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{HEIGHT}" viewBox="0 0 {width:.0f} {HEIGHT}" role="img" aria-label="{escape(diagram.title)}">',
        f"<title>{escape(diagram.title)}</title>",
        f"<style>{STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{escape(background)}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{width - 1:.0f}" height="{HEIGHT - 1}" rx="14"/>')
    parts.append(text(20, 30, diagram.title, "title", "start"))
    for i, line in enumerate(diagram.description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))

    # The refresh lines: where the first frame starts rendering, every refresh, and the end
    lines = sorted({origin, *(c.start for c in refreshes), refreshes[-1].end})
    for number, at in enumerate(lines):
        x = x_of(at)
        parts.append(f'<line class="vsync" x1="{x:.1f}" y1="{VSYNC_Y + 6}" x2="{x:.1f}" y2="{DISPLAY_Y + DISPLAY_H + 5}"/>')
        parts.append(text(x, AXIS_Y, f"{ms(at)} ms", "axis"))
        if at >= -EPSILON and at < refreshes[-1].end - EPSILON:
            parts.append(text(x, VSYNC_Y, f"{'refresh' if diagram.vrr else 'vsync'} {number - (1 if origin < 0 else 0) + 1}", "vsync-n"))

    # Row labels
    parts.append(text(20, RENDER_Y + RENDER_H / 2 - 3, "RENDER", "label", "start"))
    parts.append(text(20, RENDER_Y + RENDER_H / 2 + 13, "animation time", "vsync-n", "start"))
    parts.append(text(20, DISPLAY_Y + DISPLAY_H / 2 + 4, "DISPLAY", "label", "start"))
    for i, label in enumerate(ROW_LABELS):
        parts.append(text(20, ROWS_Y + i * ROW_STEP, label.upper(), "label", "start"))

    # Render boxes and present arrows
    for t in timed:
        x0, x1 = x_of(t.start) + 6, x_of(t.end) - 6
        parts.append(f'<rect class="box" x="{x0:.1f}" y="{RENDER_Y}" width="{x1 - x0:.1f}" height="{RENDER_H}" rx="8"/>')
        cx = (x0 + x1) / 2
        parts.append(text(cx, RENDER_Y + 19, t.frame.name, "frame"))
        parts.append(text(cx, RENDER_Y + 36, f"{ms(t.animation)} ms", "box-time"))
        ax, tip = x_of(t.end), DISPLAY_Y - 4
        parts.append(f'<line class="arrow" x1="{ax:.1f}" y1="{ARROW_Y0}" x2="{ax:.1f}" y2="{tip - 8}"/>')
        parts.append(f'<path class="arrowhead" d="M{ax - 5:.1f},{tip - 9} L{ax + 5:.1f},{tip - 9} L{ax:.1f},{tip} z"/>')

    # Display cells, and each frame's step, display time and animation error where it first appears
    previous: Timed | None = None
    for cell in refreshes:
        x0, x1 = x_of(cell.start), x_of(cell.end)
        parts.append(f'<rect class="{cell.kind}" x="{x0 + 2:.1f}" y="{DISPLAY_Y}" width="{x1 - x0 - 4:.1f}" height="{DISPLAY_H}" rx="6"/>')
        label_cls = "cell-text dark-text" if cell.kind == "again" else "cell-text"
        cx = (x0 + x1) / 2
        parts.append(text(cx, DISPLAY_Y + DISPLAY_H / 2 + 5, cell.timed.frame.name, label_cls))
        if cell.first:
            if previous is None:
                values = ("\u2013", "\u2013", "\u2013")
                error = 0.0
            else:
                step = cell.timed.animation - previous.animation
                display = cell.timed.shown - previous.shown
                error = step - display
                values = (f"{ms(step)} ms", f"{ms(display)} ms", f"{ms(error, sign=True)} ms")
            for i, value in enumerate(values):
                value_cls = ""
                if i == 2:
                    value_cls = "err" if abs(error) > EPSILON else "zero"
                    if value_cls == "err":
                        pill = len(value) * 7.4 + 18
                        parts.append(
                            f'<rect class="err-pill" x="{cx - pill / 2:.1f}" y="{ROWS_Y + i * ROW_STEP - 15}" width="{pill:.1f}" height="21" rx="10.5"/>'
                        )
                parts.append(text(cx, ROWS_Y + i * ROW_STEP, value, value_cls))
            previous = cell.timed

    # Key: what the render boxes and the arrows mean
    parts.append(f'<rect class="box" x="20" y="{LEGEND_Y - 12}" width="30" height="16" rx="4"/>')
    parts.append(text(58, LEGEND_Y + 1, "render: as wide as the frame takes, labelled with the animation time it shows", "sub", "start"))
    arrow_x = 578.0
    parts.append(f'<line class="arrow" x1="{arrow_x:.1f}" y1="{LEGEND_Y - 13}" x2="{arrow_x:.1f}" y2="{LEGEND_Y - 2}"/>')
    parts.append(f'<path class="arrowhead" d="M{arrow_x - 4:.1f},{LEGEND_Y - 3} L{arrow_x + 4:.1f},{LEGEND_Y - 3} L{arrow_x:.1f},{LEGEND_Y + 4} z"/>')
    if diagram.vrr:
        present = "present: the frame is done and handed to the display, which shows it at once"
    else:
        present = "present: the frame is done and waits for the next vsync to be shown"
    parts.append(text(arrow_x + 14, LEGEND_Y + 1, present, "sub", "start"))

    # Legend: only the colours this diagram uses
    colours_y = LEGEND_Y + 26
    x = 20.0
    used = {cell.kind for cell in refreshes}
    for kind, label in LEGEND.items():
        if kind in used:
            parts.append(f'<rect class="{kind}" x="{x:.1f}" y="{colours_y - 11}" width="14" height="14" rx="4"/>')
            parts.append(text(x + 22, colours_y + 1, label, "sub", "start"))
            x += 22 + len(label) * 6.9 + 28
    parts.append(text(20, colours_y + 26, "Animation error = animation time step \u2212 display time: + shown too soon, \u2212 shown too late", "sub", "start"))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


@dataclass(frozen=True)
class Comparison:
    """Diagrams side by side as lanes, with the display drawn the same neutral colour in each, the way a frame rate counter or a
    frame-time graph sees them: what differs is only in the animation error."""

    name: str
    title: str
    description: tuple[str, ...]
    lanes: tuple[tuple[str, str], ...]  # (lane title, diagram name)
    footer: str


LANE_TOP = 132
LANE_H = 128


def render_comparison(comparison: Comparison, background: str | None) -> str:
    lanes = [(title, DIAGRAMS_BY_NAME[name]) for title, name in comparison.lanes]
    first = lanes[0][1]
    end = cells(first, simulate(first))[-1].end

    def x_of(t: float) -> float:
        return LEFT + t * SCALE

    width = x_of(end) + RIGHT
    height = LANE_TOP + LANE_H * len(lanes) + 30
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height}" viewBox="0 0 {width:.0f} {height}" role="img" aria-label="{escape(comparison.title)}">',
        f"<title>{escape(comparison.title)}</title>",
        f"<style>{STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{escape(background)}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{width - 1:.0f}" height="{height - 1}" rx="14"/>')
    parts.append(text(20, 30, comparison.title, "title", "start"))
    for i, line in enumerate(comparison.description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))

    # One time axis on top, its refresh lines through every lane
    bottom = LANE_TOP + LANE_H * len(lanes) - 40
    for k in range(round(end / PERIOD) + 1):
        x = x_of(k * PERIOD)
        parts.append(f'<line class="vsync" x1="{x:.1f}" y1="{LANE_TOP - 14}" x2="{x:.1f}" y2="{bottom}"/>')
        parts.append(text(x, LANE_TOP - 20, f"{ms(k * PERIOD)} ms", "axis"))

    for lane, (title, diagram) in enumerate(lanes):
        top = LANE_TOP + lane * LANE_H
        parts.append(text(20, top + 20, title, "lane", "start"))
        parts.append(text(20, top + 36, f"{1000 / PERIOD:.0f} fps, {ms(PERIOD)} ms frametimes", "vsync-n", "start"))
        parts.append(text(20, top + 66, "DISPLAY TIME", "label", "start"))
        parts.append(text(20, top + 92, "ANIMATION ERROR", "label", "start"))
        previous: Timed | None = None
        for cell in cells(diagram, simulate(diagram)):
            x0, x1 = x_of(cell.start), x_of(cell.end)
            cx = (x0 + x1) / 2
            parts.append(f'<rect class="neutral" x="{x0 + 2:.1f}" y="{top}" width="{x1 - x0 - 4:.1f}" height="40" rx="6"/>')
            parts.append(text(cx, top + 18, cell.timed.frame.name, "cell-text"))
            parts.append(text(cx, top + 34, f"{ms(cell.timed.animation)} ms", "box-time"))
            if previous is None:
                display, error_text, error = "–", "–", 0.0
            else:
                display = f"{ms(cell.timed.shown - previous.shown)} ms"
                error = cell.timed.animation - previous.animation - (cell.timed.shown - previous.shown)
                error_text = f"{ms(error, sign=True)} ms"
            parts.append(text(cx, top + 66, display, "same" if previous is not None else ""))
            if abs(error) > EPSILON:
                pill = len(error_text) * 7.4 + 18
                parts.append(f'<rect class="err-pill" x="{cx - pill / 2:.1f}" y="{top + 77}" width="{pill:.1f}" height="21" rx="10.5"/>')
                parts.append(text(cx, top + 92, error_text, "err"))
            else:
                parts.append(text(cx, top + 92, error_text, "zero"))
            previous = cell.timed

    parts.append(text(20, height - 22, comparison.footer, "sub", "start"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


SLOW = (Frame("A", 75), Frame("B", 125), Frame("C", 75), Frame("D", 75), Frame("E", 125), Frame("F", 75))

DIAGRAMS = (
    Diagram(
        "perfect-timer",
        "Perfect timer, every frame on time",
        (
            "Each frame shows the moment it is displayed: the animation time step equals the display time, so the animation error is 0.",
            "A 10 Hz display with vsync (a refresh every 100 ms): a slowed-down 60 Hz.",
        ),
        tuple(Frame(name, 75) for name in "ABCDEFGH"),
    ),
    Diagram(
        "timer-jitter",
        "Timer jitter: frames on time, animation time off",
        (
            "Frame rate, frametimes and display times are identical to the perfect timer's, but the game's clock is read at an uneven",
            "point after each flip, so each frame shows a moment a little off: delta time jitter. Only the animation error reveals it.",
        ),
        tuple(Frame(name, 75, timer_error=error) for name, error in zip("ABCDEFGH", (0, 0.2, 2.4, -1, 0.8, -1, 0.6, 0.2), strict=True)),
    ),
    Diagram(
        "slow-frames",
        "Slow frames: animation time right, frames late",
        (
            "B and E take longer than a refresh. The previous frame is held, the late frame shows a moment already past (shown too late),",
            "and the next one catches up by jumping twice as far (shown too soon): a hitch, seen as stutter.",
        ),
        SLOW,
    ),
    Diagram(
        "half-rate-even",
        "Half rate, evenly paced",
        (
            "Each frame is meant to stay for two refreshes (swap interval 2), like 30 fps on a 60 Hz display, and it does:",
            "every step is 200 ms and every frame is on screen for 200 ms.",
        ),
        tuple(Frame(name, 150, interval=2) for name in "ABCD"),
    ),
    Diagram(
        "half-rate-bad-pacing",
        "Half rate, bad frame pacing",
        (
            "The game steps its animation 200 ms per frame, but the frames are shown for 1 and 3 refreshes instead of 2 each:",
            "Digital Foundry's bad 30 fps frame pacing (16.7 and 50 ms frames on 60 Hz). The average frame rate is still half.",
        ),
        (Frame("A", 75), Frame("B", 75), Frame("C", 250), Frame("D", 75), Frame("E", 250)),
        fixed_step=200,
    ),
    Diagram(
        "vrr-slow-frames",
        "VRR with the same slow frames",
        (
            "The display refreshes as soon as a frame is presented (at most every 100 ms). B and E appear when they are done instead",
            "of at the next vsync, so the errors shrink, but a slow frame is still late: VRR does not remove the hitch.",
        ),
        SLOW,
        vrr=True,
    ),
)
DIAGRAMS_BY_NAME = {diagram.name: diagram for diagram in DIAGRAMS}

COMPARISONS = (
    Comparison(
        "perfect-vs-jitter",
        "Same frame rate, same frametimes, different motion",
        (
            "A perfect timer and a jittery one, measured the usual way: 10 fps, every frame on screen for exactly 100 ms, a flat frame-time",
            "graph. Every one of those numbers is identical. Only the animation time inside each frame differs, and only animation error shows it.",
        ),
        (("Perfect timer", "perfect-timer"), ("Timer jitter", "timer-jitter")),
        "The eye sees the jittered frames as slightly uneven motion; frame rate and frametime cannot explain why, animation error does.",
    ),
)
# Every output by name, as a function of the background: the diagrams and the comparisons
RENDERERS: dict[str, Callable[[str | None], str]] = {
    **{diagram.name: functools.partial(render, diagram) for diagram in DIAGRAMS},
    **{comparison.name: functools.partial(render_comparison, comparison) for comparison in COMPARISONS},
}


def find_browser() -> str:
    """A Chromium browser for --png: MB_BROWSER, the usual install locations, then PATH."""
    configured = os.environ.get(BROWSER_ENVIRONMENT_VARIABLE)
    if configured:
        if not Path(configured).is_file():
            raise SystemExit(f"{BROWSER_ENVIRONMENT_VARIABLE} does not point to a file: {configured}")
        return configured
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(f"--png needs Edge or Chrome: set {BROWSER_ENVIRONMENT_VARIABLE} to its executable")


def save_png(browser: str, svg: Path, png: Path, background: str | None) -> None:
    """Screenshot the SVG in a headless browser at 2x, with a transparent background unless one is set."""
    content = svg.read_text(encoding="utf-8")
    width = int(content.split('width="', 1)[1].split('"', 1)[0])
    height = int(content.split('height="', 1)[1].split('"', 1)[0])
    with tempfile.TemporaryDirectory() as profile:
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"--screenshot={png.resolve()}",
            svg.resolve().as_uri(),
        ]
        if not background:
            command.insert(1, "--default-background-color=00000000")
        _ = subprocess.run(command, check=True, capture_output=True, timeout=60)


class Arguments(argparse.Namespace):
    names: list[str]
    output_dir: Path
    png: bool
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the timing diagrams (SVG, optionally PNG).")
    _ = parser.add_argument("names", nargs="*", metavar="NAME", help=f"diagrams to generate (default: all): {', '.join(RENDERERS)}")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the files go (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x of each, through a headless Edge or Chrome")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, such as #ffffff, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    names = args.names or list(RENDERERS)
    for name in names:
        if name not in RENDERERS:
            parser.error(f"unknown diagram '{name}': use {', '.join(RENDERERS)}")
    browser = find_browser() if args.png else None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = args.output_dir / f"timing-{name}.svg"
        _ = path.write_text(RENDERERS[name](args.background), encoding="utf-8", newline="\n")
        print(path)
        if browser:
            png = path.with_suffix(".png")
            save_png(browser, path, png, args.background)
            print(png)


if __name__ == "__main__":
    main()
