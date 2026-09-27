#!/usr/bin/env python3
"""Generate the adaptive rate charts: how a Swappy-like rule decides the swap interval, frame by frame, from the simulation of
tools/frame_pacing_video/adaptive_rate.py.
- chart-adaptive-rate.svg: the busy stretch of the adapt the rate video at 60 Hz, half rate and back;
- chart-adaptive-rate-100hz.svg: at 100 Hz a load that rises in three steps and falls back, each step needing one more refresh, so
  the rule steps down through 50, 33 and 25 fps and back up.

Four rows on one time axis: each frame's render time, against whole refreshes, a missed frame in red; the share of the last 2 s of
frames that missed, with the 10 % the rule slows down at; their average render time plus 1 ms, with the line it has to be under to
speed up (one interval shorter, less 1 ms); and the swap interval the frames are paced at. After each change the rule starts a new
2 s window and decides nothing until it holds 2 s: that window is drawn dashed, and so are the values while it fills.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_adaptive_rate.py [--output-dir DIR] [--png] [--background COLOUR]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from generate_diagrams import DEFAULT_OUTPUT_DIR, STYLE, find_browser, save_png, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frame_pacing_video"))

from adaptive_rate import CALM_MS, DROP_THRESHOLD, FRAME_MARGIN_MS, STAGES, WINDOW_S, Record, Stage, with_lead  # noqa: E402


@dataclass(frozen=True)
class Scenario:
    """One chart: the display's refresh rate, the clip's length, the load's stages, and how the chart shows them."""

    file: str
    title: str
    description: tuple[str, ...]
    fps: int
    seconds: int
    stages: tuple[Stage, ...]
    calm: tuple[float, float]
    stage_labels: tuple[str, ...]
    render_top_ms: float
    average_range: tuple[float, float]
    # The window each decision was made on, drawn too (where changes are far apart; with many, it is the filling one before)
    decided_windows: bool
    second_step: int
    # The clip loops (a video's): a window running past its end continues at its start
    loops: bool = True

    @property
    def refreshes(self) -> int:
        return self.fps * self.seconds

    @property
    def refresh_ms(self) -> float:
        return 1000 / self.fps


def _stages_100hz() -> tuple[Stage, ...]:
    """At 100 Hz, of 24 s: 1.5 to 5.5 s one refresh too slow, then two, then three, then back down."""

    def at(seconds: float) -> Fraction:
        return Fraction(round(seconds * 10), 240)

    levels: tuple[tuple[float, float, tuple[float, float]], ...] = (
        (1.5, 5.5, (13.0, 17.0)),
        (5.5, 9.5, (22.0, 27.0)),
        (9.5, 13.5, (31.0, 37.0)),
        (13.5, 17.0, (22.0, 27.0)),
        (17.0, 20.5, (13.0, 17.0)),
    )
    return tuple((at(start), at(end), times) for start, end, times in levels)


SCENARIOS = (
    Scenario(
        "chart-adaptive-rate.svg",
        "How the rate adapts, frame by frame",
        (
            f"The busy stretch of the video, with a rule like Swappy's. It keeps the frames of the last {WINDOW_S:g} s: when more than {DROP_THRESHOLD} % of them",
            f"missed, it drops to half rate; when none missed and their average render time plus {FRAME_MARGIN_MS:g} ms fits a refresh with {FRAME_MARGIN_MS:g} ms to spare,",
            f"it goes back up. After each change it starts a new {WINDOW_S:g} s window, and decides nothing until that holds {WINDOW_S:g} s of frames.",
            "Blue: the window a decision was made on. Dashed: a new window filling, its values dashed while the rule does not use them yet.",
        ),
        60,
        8,
        STAGES,
        CALM_MS,
        ("the busy stretch",),
        36.0,
        (10.0, 20.0),
        True,
        1,
    ),
    Scenario(
        "chart-adaptive-rate-100hz.svg",
        "At 100 Hz: many steps, each a new window",
        (
            "The same rule at 100 Hz, a refresh every 10 ms, with a load that rises in three steps and falls back. More than 10 % of a full window",
            "missed: it slows to the interval the average frame time needs, 100, 50, 33 and then 25 fps. None missed and the average fits one",
            "interval shorter, less 1 ms: it speeds up a step. Every change starts a new 2 s window (dashed), and nothing is decided until it is full:",
            "a change can follow the one before it no sooner than 2 s later, however many frames miss meanwhile.",
        ),
        100,
        24,
        _stages_100hz(),
        (5.0, 8.0),
        ("one refresh too slow", "two", "three", "two", "one"),
        45.0,
        (5.0, 40.0),
        False,
        2,
        loops=False,
    ),
)

WIDTH = 1180
PLOT_X0 = 190
PLOT_X1 = WIDTH - 150
TOP = 176
ROW_H = 96
ROW_GAP = 30

CHART_STYLE = """
  .grid { stroke: #ffffff; stroke-opacity: 0.1; stroke-width: 1; }
  .busy-band { fill: #d29922; fill-opacity: 0.6; }
  .busy-text { fill: #d29922; font-size: 12px; }
  .decided { fill: #58a6ff; fill-opacity: 0.07; stroke: #58a6ff; stroke-opacity: 0.8; stroke-width: 1.5; }
  .decided-text { fill: #58a6ff; font-size: 12px; font-weight: 600; }
  .filling { fill: #8b949e; fill-opacity: 0.04; stroke: #8b949e; stroke-width: 1.5; stroke-dasharray: 6 4; }
  .filling-text { fill: #8b949e; font-size: 12px; }
  .value-filling { stroke: #58a6ff; stroke-opacity: 0.5; stroke-width: 1.5; stroke-dasharray: 4 3; fill: none; }
  .ok { fill: #2ea043; }
  .miss { fill: #e5534b; }
  .limit { stroke: #d29922; stroke-width: 1.5; stroke-dasharray: 6 4; fill: none; }
  .limit-text { fill: #d29922; font-size: 12px; }
  .value { stroke: #58a6ff; stroke-width: 2; fill: none; stroke-linejoin: round; }
  .change { stroke: #e6edf3; stroke-opacity: 0.55; stroke-width: 1.5; stroke-dasharray: 3 4; }
  .change-text { fill: #e6edf3; font-size: 12px; font-weight: 600; }
"""


def row_top(row: int) -> float:
    return TOP + row * (ROW_H + ROW_GAP)


@dataclass(frozen=True)
class Windows:
    """The rule's window through the clip, rebuilt the way Swappy keeps it: each frame's missed share and average plus the margin
    over the window after it (also while the window fills, when the rule does not use them), and for each change, by the refresh
    it was made on, the refresh its window began on."""

    missed: list[float]
    average: list[float]
    decided_from: dict[int, int]


def windows(scenario: Scenario, timeline: list[Record]) -> Windows:
    """From the frames with the pass before the clip in front, so the window at the start holds what the simulation's did."""
    lead = sum(1 for frame in timeline if frame.shown < 0)
    window: list[Record] = []
    missed: list[float] = []
    average: list[float] = []
    decided_from: dict[int, int] = {}
    fps = float(scenario.fps)
    for index, frame in enumerate(timeline):
        window.append(frame)
        # In seconds, as floats, counted from the start of the simulation as it counts them, so they compare exactly the same
        while len(window) >= 2 and (frame.shown + scenario.refreshes) / fps - (window[1].shown + scenario.refreshes) / fps > WINDOW_S:
            _ = window.pop(0)
        if index >= lead:
            missed.append(100 * sum(f.missed for f in window) / len(window))
            average.append(sum(f.render_ms for f in window) / len(window) + FRAME_MARGIN_MS)
            if frame.change is not None:
                decided_from[frame.shown] = window[0].shown
        if frame.change is not None:
            window = []
    return Windows(missed, average, decided_from)


def render(scenario: Scenario, background: str | None) -> str:
    timeline = with_lead("swappy", scenario.refreshes, Fraction(scenario.fps), scenario.stages, scenario.calm)
    frames = [frame for frame in timeline if frame.shown >= 0]
    rule = windows(scenario, timeline)
    refreshes, refresh_ms = scenario.refreshes, scenario.refresh_ms
    intervals = sorted({frame.interval for frame in frames})

    def x_of(refresh: float) -> float:
        return PLOT_X0 + refresh / refreshes * (PLOT_X1 - PLOT_X0)

    def fps_at(interval: int) -> str:
        return f"{scenario.fps / interval:.0f} fps"

    height = row_top(4) + 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{scenario.title}">',
        f"<title>{scenario.title}</title>",
        f"<style>{STYLE}{CHART_STYLE}</style>",
    ]
    if background:
        parts.append(f'<rect width="100%" height="100%" fill="{background}"/>')
    parts.append(f'<rect class="card" x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="14"/>')
    parts.append(text(20, 30, scenario.title, "title", "start"))
    for i, line in enumerate(scenario.description):
        parts.append(text(20, 54 + i * 19, line, "sub", "start"))

    # The windows, over the rows they are about: the one each decision was made on, and the new one it starts, filling (the one
    # running past the end of the clip continues at its start)
    band_top, band_bottom = row_top(0) - 6, row_top(2) + ROW_H + 6

    def band(start: float, end: float, kind: str, label: str) -> None:
        pieces = ((start, float(refreshes)), (0.0, end - refreshes)) if end > refreshes and scenario.loops else ((start, min(end, refreshes)),)
        for a, b in pieces:
            if b <= a:
                continue
            parts.append(f'<rect class="{kind}" x="{x_of(a):.1f}" y="{band_top}" width="{x_of(b) - x_of(a):.1f}" height="{band_bottom - band_top}"/>')
            # The label on the piece that starts the band, not on the rest of one carried over from the end of the clip
            if a == start:
                parts.append(text(x_of(a) + 6, band_top - 6, label, f"{kind}-text", "start"))

    window_refreshes = WINDOW_S * scenario.fps
    for frame in frames:
        if frame.change is not None:
            if scenario.decided_windows:
                band(rule.decided_from[frame.shown], frame.shown + 1, "decided", "window it decided on")
            label = "new window, filling: no decision" if scenario.decided_windows else "new window"
            band(frame.shown + 1, frame.shown + 1 + window_refreshes, "filling", label)

    def row(index: int, name: str, sub: str, low: float, high: float) -> Callable[[float], float]:
        top = row_top(index)
        bottom = top + ROW_H
        parts.append(text(20, top + ROW_H / 2 - 4, name, "label", "start"))
        parts.append(text(20, top + ROW_H / 2 + 12, sub, "vsync-n", "start"))
        parts.append(f'<line class="grid" x1="{PLOT_X0}" y1="{bottom}" x2="{PLOT_X1}" y2="{bottom}"/>')

        def y_of(value: float) -> float:
            return bottom - (min(max(value, low), high) - low) / (high - low) * ROW_H

        return y_of

    def limit(y: float, label: str) -> None:
        parts.append(f'<line class="limit" x1="{PLOT_X0}" y1="{y:.1f}" x2="{PLOT_X1}" y2="{y:.1f}"/>')
        parts.append(text(PLOT_X1 + 8, y + 4, label, "limit-text", "start"))

    def polylines(values: list[float], y_of: Callable[[float], float]) -> list[str]:
        """Solid where the rule uses the values (its window holds 2 s), dashed where it does not yet (a new window filling)."""
        runs: list[tuple[bool, list[str]]] = []
        for frame, value in zip(frames, values, strict=True):
            used = frame.missed_percent is not None
            point = f"{x_of(frame.shown):.1f},{y_of(value):.1f}"
            if runs and runs[-1][0] == used:
                runs[-1][1].append(point)
            else:
                # Each run starts where the last one ended, so the line has no gap
                runs.append((used, ([runs[-1][1][-1]] if runs else []) + [point]))
        return [f'<polyline class="{"value" if used else "value-filling"}" points="{" ".join(run)}"/>' for used, run in runs if len(run) > 1]

    # 1: render times, a bar per frame from the refresh it is shown on
    y_of = row(0, "RENDER TIME", "each frame", 0, scenario.render_top_ms)
    bottom = row_top(0) + ROW_H
    for frame in frames:
        y = y_of(frame.render_ms)
        width = max(1.0, x_of(frame.shown + 1) - x_of(frame.shown) - 0.6)
        parts.append(
            f'<rect class="{"miss" if frame.missed else "ok"}" x="{x_of(frame.shown):.1f}" y="{y:.1f}" width="{width:.1f}" height="{bottom - y:.1f}"/>'
        )
    count = 1
    while count * refresh_ms <= scenario.render_top_ms:
        limit(y_of(count * refresh_ms), "one refresh" if count == 1 else f"{count} refreshes")
        count += 1

    # 2: the share of the window that missed
    y_of = row(1, "MISSED", f"of the last {WINDOW_S:g} s", 0, 30)
    parts += polylines(rule.missed, y_of)
    limit(y_of(DROP_THRESHOLD), f"{DROP_THRESHOLD} %: slower")
    parts.append(text(PLOT_X0 - 10, y_of(0) + 4, "0 %", "vsync-n", "end"))
    parts.append(text(PLOT_X0 - 10, y_of(30) + 4, "30 %", "vsync-n", "end"))

    # 3: the average render time plus the margin, and the line it has to be under to speed up: one interval shorter, less the
    # margin, so it steps with the interval (none at full rate)
    low, high = scenario.average_range
    y_of = row(2, "AVERAGE + 1 MS", f"of the last {WINDOW_S:g} s", low, high)
    parts += polylines(rule.average, y_of)
    runs: list[list[str]] = []
    for index, frame in enumerate(frames):
        end = frames[index + 1].shown if index + 1 < len(frames) else refreshes
        paced = frames[index + 1].interval if index + 1 < len(frames) else frame.interval
        if paced == 1:
            runs.append([])
            continue
        y = y_of(refresh_ms * (paced - 1) - FRAME_MARGIN_MS)
        if not runs:
            runs.append([])
        runs[-1] += [f"{x_of(frame.shown):.1f},{y:.1f}", f"{x_of(end):.1f},{y:.1f}"]
    for run in runs:
        if run:
            parts.append(f'<polyline class="limit" points="{" ".join(run)}"/>')
    parts.append(text(PLOT_X1 + 8, y_of(high) + 14, "under the dashed", "limit-text", "start"))
    parts.append(text(PLOT_X1 + 8, y_of(high) + 30, "line: faster", "limit-text", "start"))
    parts.append(text(PLOT_X0 - 10, y_of(low) + 4, f"{low:g} ms", "vsync-n", "end"))
    parts.append(text(PLOT_X0 - 10, y_of(high) + 4, f"{high:g} ms", "vsync-n", "end"))

    # 4: the swap interval, a step line
    y_of = row(3, "SWAP INTERVAL", "refreshes per frame", 0.5, max(intervals) + 0.5)
    points: list[str] = []
    for frame in frames:
        y = y_of(frame.interval)
        if points:
            points.append(f"{x_of(frame.shown):.1f},{float(points[-1].split(',')[1]):.1f}")
        points.append(f"{x_of(frame.shown):.1f},{y:.1f}")
    points.append(f"{x_of(refreshes):.1f},{y_of(frames[-1].interval):.1f}")
    parts.append(f'<polyline class="value" points="{" ".join(points)}"/>')
    for interval in range(1, max(intervals) + 1):
        parts.append(text(PLOT_X0 - 10, y_of(interval) + 4, f"{interval}: {fps_at(interval)}", "vsync-n", "end"))

    # The changes, through every row
    for index, frame in enumerate(frames):
        if frame.change is None:
            continue
        x = x_of(frame.shown + 1)
        parts.append(f'<line class="change" x1="{x:.1f}" y1="{row_top(0) - 4}" x2="{x:.1f}" y2="{row_top(4) - 18}"/>')
        after = frames[index + 1].interval if index + 1 < len(frames) else frame.interval
        if scenario.decided_windows:
            label = (
                f"{frame.missed_percent} % missed: half rate"
                if frame.change == "slower"
                else f"none missed, {frame.average_ms + FRAME_MARGIN_MS:.1f} ms fits: full rate"  # pyright: ignore[reportOptionalOperand]
            )
        else:
            label = f"→ {fps_at(after)}"
        parts.append(text(x + 6, row_top(3) + 14, label, "change-text", "start"))

    # The load's stages, on the time axis
    for (start, end, _), label in zip(scenario.stages, scenario.stage_labels, strict=True):
        x0, x1 = x_of(float(start * refreshes)), x_of(float(end * refreshes))
        parts.append(f'<rect class="busy-band" x="{x0:.1f}" y="{row_top(4) - 16}" width="{x1 - x0 - 2:.1f}" height="5"/>')
        if len(scenario.stages) == 1:
            parts.append(text(x1 + 8, row_top(4) - 10, label, "busy-text", "start"))
        else:
            parts.append(text((x0 + x1) / 2, row_top(4) - 22, label, "busy-text", "middle"))
    for second in range(0, scenario.seconds + 1, scenario.second_step):
        parts.append(text(x_of(second * scenario.fps), row_top(4) + 12, f"{second} s", "vsync-n", "middle"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Arguments(argparse.Namespace):
    output_dir: Path
    png: bool
    background: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the adaptive rate charts (SVG, optionally PNG).")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the files go (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x, through a headless Edge or Chrome")
    _ = parser.add_argument("--background", default=None, help="a page colour behind the card, such as #ffffff, for previews (default: transparent)")
    args = parser.parse_args(namespace=Arguments())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for scenario in SCENARIOS:
        path = args.output_dir / scenario.file
        _ = path.write_text(render(scenario, args.background), encoding="utf-8", newline="\n")
        print(path)
        if args.png:
            png = path.with_suffix(".png")
            save_png(find_browser(), path, png, args.background)
            print(png)


if __name__ == "__main__":
    main()
