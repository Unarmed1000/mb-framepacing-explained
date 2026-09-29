#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate the measured example charts of doc/charts.md: mb-framepacing's report card of a video mode, as a capture card sees it.

For each mode the marked single-box clip is rendered (as export_test_clips.py makes them for mb-framepacing's tests), mb-framepacing
imports and analyses it (every frame's display time from the video, its animation time from its marker) and draws its report card
with what the charts page shows:

- the display and five headline tiles: average fps, 1 % low, frames visibly off, error p99, worst error;
- the animation error per frame, as signed bars around zero;
- the display time step with the animation time step over it (an even display with an uneven animation is delta time jitter);
- the refresh strip of the first second: one cell per refresh, a new shade with each new frame.

The 60-naive-heavy card also gets its animation error histogram. The numbers are a measurement: the clip's first frame has no display
time step (in the looping video it follows the clip's last frame), so a clip of 480 frames has 479 steps.

With --test-clips it measures mb-framepacing's test clips instead (export_test_clips.py, each at its speed; default all of them) and
keeps mb-framepacing's default report card, as the app draws it for a capture, titled with the clip's mode:
doc/images/test-clip-<mode>.svg, for the web page's "test clips, measured" slide.

mb-framepacing comes from the submodule external/mb-framepacing (the commit this repository pins): the script builds it there with
dotnet build -c Release (incremental; its bin/ and obj/ are ignored by the submodule's git). --mb-framepacing, the MB_FRAMEPACING
environment variable or local.toml ([mb-framepacing] path) name another build instead. The clips and the captures stay in
out/measured_charts.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_measured_charts.py [--output-dir DIR] [--png] [MODE ...]
  python tools/timing_diagrams/generate_measured_charts.py --test-clips [MODE ...]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frame_pacing_video"))

import export_test_clips  # noqa: E402
import generate_videos as gv  # noqa: E402
from frame_timing import TimingParameters, describe, parse_mode  # noqa: E402
from generate_diagrams import DEFAULT_OUTPUT_DIR  # noqa: E402

DEFAULT_MODES = ("60-naive-light", "60-naive-heavy", "60-naive-heavy-realistic")
# The modes that also get their animation error histogram
HISTOGRAM_MODES = ("60-naive-heavy",)
WORK_DIR = gv.REPO_ROOT / "out" / "measured_charts"
SUBMODULE_PROJECT = gv.REPO_ROOT / "external" / "mb-framepacing" / "measure" / "app" / "FramePacing" / "FramePacing.csproj"
SUBMODULE_BUILD = SUBMODULE_PROJECT.parent / "bin" / "Release" / "net10.0"

MB_FRAMEPACING = gv.Tool(
    "mb-framepacing",
    "mb-framepacing",
    "--mb-framepacing",
    "MB_FRAMEPACING",
    "Run git submodule update --init (the script builds external/mb-framepacing)",
)

# The report card's items (mb-framepacing render --only), and its layout for the page
REPORT_ITEMS = (
    "title",
    "display",
    "average-fps",
    "one-percent-low",
    "frames-off",
    "error-p99",
    "worst-error",
    "animation-error",
    "display-time-step",
    "refresh-strip",
)
REPORT_LAYOUT = ("--show", "animation-time-step", "--strip-seconds", "1", "--tiles-per-row", "5")


class Arguments(argparse.Namespace):
    modes: list[str]
    output_dir: Path
    png: bool
    test_clips: bool
    mb_framepacing: str | None
    ffmpeg: str | None
    config: Path | None


def title(mode: str) -> str:
    """The card's title: the mode and what it is ("60-naive-heavy: 60 Hz naive timer, heavy load")."""
    return f"{mode}: {describe(parse_mode(mode), TimingParameters())}"


def render_options(mode: str, png: bool) -> list[str]:
    """mb-framepacing render's options for a charts page card: the report card, and the error histogram for the histogram modes."""
    cards = "error-histogram" if mode in HISTOGRAM_MODES else "none"
    options = ["--cards", cards, "--only", ",".join(REPORT_ITEMS), *REPORT_LAYOUT, "--title", title(mode)]
    return [*options, "--png"] if png else options


def outputs(mode: str, png: bool) -> list[tuple[str, str]]:
    """The files render writes (run 1), with the names they get in the output folder."""
    names = [("run-1-report", f"report-{mode}")]
    if mode in HISTOGRAM_MODES:
        names.append(("run-1-error-histogram", f"error-histogram-{mode}"))
    suffixes = (".svg", ".png") if png else (".svg",)
    return [(source + suffix, target + suffix) for source, target in names for suffix in suffixes]


def run(command: list[str]) -> None:
    """Run a tool quietly; its output is shown when it fails."""
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        raise gv.ToolError(f"{Path(command[0]).name} {command[1]} failed (exit code {result.returncode}):\n{result.stdout}{result.stderr}".rstrip())


def submodule_tool() -> Path:
    """Build mb-framepacing in the submodule (incremental) and return its executable."""
    if not SUBMODULE_PROJECT.is_file():
        raise gv.ToolError(f"{SUBMODULE_PROJECT} is missing: run git submodule update --init")
    run(["dotnet", "build", str(SUBMODULE_PROJECT), "-c", "Release", "--nologo", "-v", "quiet"])
    tool = gv.resolve_tool(SUBMODULE_BUILD, MB_FRAMEPACING.name)
    if tool is None:
        raise gv.ToolError(f"the build did not make mb-framepacing in {SUBMODULE_BUILD}")
    return tool


def find_mb_framepacing(explicit: str | None, config: Path | None) -> Path:
    """mb-framepacing: where it was given (--mb-framepacing, MB_FRAMEPACING, local.toml), else the submodule's, built."""
    configured = gv.configured_tool(MB_FRAMEPACING, explicit, config)
    return configured.path if configured is not None else submodule_tool()


def measure_clip(settings: gv.Settings, job: gv.VideoJob, tool: Path, ffmpeg: Path, render: list[str]) -> Path:
    """Render a marked clip, have mb-framepacing import and analyse it, and draw it with the render options `render`; returns the
    folder render wrote to (out/measured_charts/<mode>/render)."""
    work = WORK_DIR / job.top.name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    video = work / "video.mp4"
    gv.encode_video(ffmpeg, settings, job, video)
    capture = work / "capture"
    run([str(tool), "import", str(video), "-o", str(capture), "--analyze"])
    rendered = work / "render"
    run([str(tool), "render", str(capture), "-o", str(rendered), *render])
    return rendered


def measure(mode: str, tool: Path, ffmpeg: Path, output_dir: Path, png: bool) -> list[Path]:
    """Render mode's marked clip, measure it with mb-framepacing and copy its cards to output_dir."""
    _, settings = gv.parse_arguments(["--single", mode, "--marker", "--speed", "fast"])
    (job,) = gv.plan_videos(settings)
    rendered = measure_clip(settings, job, tool, ffmpeg, render_options(mode, png))
    written: list[Path] = []
    for source, target in outputs(mode, png):
        path = output_dir / target
        _ = shutil.copyfile(rendered / source, path)
        written.append(path)
    return written


def test_clip_render(mode: str, png: bool) -> list[str]:
    """The render options of a test clip's card: mb-framepacing's default report card, titled with the clip's mode (its folder in
    mb-framepacing's test-data/videos; a title with the mode's description would run under the card's display box), without
    distribution cards."""
    return ["--cards", "none", "--title", mode, *(["--png"] if png else [])]


def test_clip_name(mode: str) -> str:
    return f"test-clip-{mode}"


def measure_test_clips(modes: list[str], tool: Path, ffmpeg: Path, output_dir: Path, png: bool) -> list[Path]:
    """Measure the test clips named (default: all of export_test_clips.SCENARIOS, each at its speed) and copy their report cards to
    output_dir as test-clip-<mode>.svg."""
    clips = [(settings, job) for settings, job in export_test_clips.planned() if not modes or job.top.name in modes]
    written: list[Path] = []
    for index, (settings, job) in enumerate(clips, start=1):
        mode = job.top.name
        print(f"[{index}/{len(clips)}] {mode}", flush=True)
        rendered = measure_clip(settings, job, tool, ffmpeg, test_clip_render(mode, png))
        for suffix in (".svg", ".png") if png else (".svg",):
            path = output_dir / (test_clip_name(mode) + suffix)
            _ = shutil.copyfile(rendered / ("run-1-report" + suffix), path)
            print(path)
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the measured example charts: mb-framepacing's report cards of video modes.")
    _ = parser.add_argument("modes", nargs="*", metavar="MODE", help=f"video modes to measure (default: {', '.join(DEFAULT_MODES)})")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the cards go (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x of each, through a headless Edge or Chrome")
    _ = parser.add_argument(
        "--test-clips", action="store_true", help="measure the test clips (MODE: some of them; default all) as test-clip-<mode>.svg, the default report card"
    )
    _ = parser.add_argument(
        "--mb-framepacing", metavar="PATH", help="mb-framepacing executable or its folder (default: MB_FRAMEPACING, local.toml, then the submodule's, built)"
    )
    _ = parser.add_argument("--ffmpeg", metavar="PATH", help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    _ = parser.add_argument("--config", type=Path, metavar="FILE", help="machine-local settings file (default: local.toml in the repository root)")
    args = parser.parse_args(argv, namespace=Arguments())
    modes = args.modes if args.test_clips else args.modes or list(DEFAULT_MODES)
    unknown = [mode for mode in modes if mode not in export_test_clips.SCENARIOS] if args.test_clips else []
    if unknown:
        parser.error(f"not a test clip: {', '.join(unknown)} (the test clips are export_test_clips.SCENARIOS)")
    for mode in modes:
        try:
            _ = parse_mode(mode)
        except ValueError as error:
            parser.error(str(error))
    try:
        tool = find_mb_framepacing(args.mb_framepacing, args.config)
        ffmpeg = gv.find_ffmpeg(args.ffmpeg, args.config).path
        gv.require_lossless_encoder(gv.list_encoders(ffmpeg), ffmpeg)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.test_clips:
            _ = measure_test_clips(modes, tool, ffmpeg, args.output_dir, args.png)
            return 0
        for index, mode in enumerate(modes, start=1):
            print(f"[{index}/{len(modes)}] {mode}", flush=True)
            for path in measure(mode, tool, ffmpeg, args.output_dir, args.png):
                print(path)
    except (gv.ToolError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
