#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Rene Thrane
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Everything this repository takes from mb-framepacing: its charts and its verdicts, measured from the clips. The one place for it,
so a new chart or export is added here (an export of EXPORTS: a flag, and what it measures and writes). mb-framepacing's rule of
which frame is late and which is delta time jitter lives in mb-framepacing only; this repository draws no animation error chart of
its own rule.

- the report cards of doc/charts.md (MODE ..., the default);
- --test-clips: the test clips' report cards, for the "test clips, measured" slides;
- --playback-example: the web page's live playback report;
- --timelines: the timing diagrams as mb-framepacing's frame timeline card (render --timeline) of each diagram's replay clip;
- --web-verdicts: each frame's verdict (late, delta time jitter, within the error threshold, another error) of every clip the web
  page charts, for its live animation error and display time step charts (web/src/charts/verdicts.json);
- --all: every export the pages use.

The report cards: for each mode the marked single-box clip is rendered (as export_test_clips.py makes them for mb-framepacing's tests), mb-framepacing
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
doc/images/test-clip-<mode>.svg, for the web page's "test clips, measured" slides.

With --playback-example it writes the web page's live playback report instead: mb-framepacing's playback page of the test clip
60-busy-adaptive (the recording next to its report card, with a player), web/public/playback/60-busy-adaptive/index.html. The page
plays the clip's web-encoded copy, which build_blind_test.py makes into web/public/videos with the page's other clips (the same
frames and timestamps): it names it by a path relative to itself (--playback-video-url), so no video goes into the folder. The
folder's playback.json is left out: the page does not read it.

With --timelines (NAME ...: some diagrams; default every replayable one, diagram_replay.replayable(); a VRR diagram cannot be
replayed) it renders each diagram's marked clip 60-diagram-<name>-every-1s, which plays the whole diagram once a second, and draws
the first copy's refreshes with render --timeline: doc/images/timeline-<name>.svg.

With --web-verdicts it measures, for every clip the web page charts (trials.json and clips.json, as build_blind_test.py collects
them: a mode in a motion), the marked single-box clip of the same frames (the page's timing arguments, TIMING_ARGUMENTS; the clips
must agree frame by frame, or it stops), and writes one letter per frame of the clip from run-1-frames.csv's flags (VERDICTS):
web/src/charts/verdicts.json. The run's first frame has no step in the measurement (in the looping video it follows the clip's last
frame): it gets none.

mb-framepacing comes from the submodule external/mb-framepacing (the commit this repository pins): the script builds it there with
dotnet build -c Release (incremental; its bin/ and obj/ are ignored by the submodule's git). --mb-framepacing, the MB_FRAMEPACING
environment variable or local.toml ([mb-framepacing] path) name another build instead. The clips and the captures stay in
out/measured_charts.

Run from the repository's .venv:
  python tools/timing_diagrams/generate_measured_charts.py [--output-dir DIR] [--png] [MODE ...]
  python tools/timing_diagrams/generate_measured_charts.py --test-clips [MODE ...]
  python tools/timing_diagrams/generate_measured_charts.py --playback-example
  python tools/timing_diagrams/generate_measured_charts.py --timelines [--png] [NAME ...]
  python tools/timing_diagrams/generate_measured_charts.py --web-verdicts
  python tools/timing_diagrams/generate_measured_charts.py --all
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frame_pacing_video"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web_export"))

import build_blind_test  # noqa: E402
import diagram_replay  # noqa: E402
import export_test_clips  # noqa: E402
import generate_videos as gv  # noqa: E402
from frame_timing import TimingParameters, describe, parse_mode, swap_interval  # noqa: E402
from generate_diagrams import DEFAULT_OUTPUT_DIR  # noqa: E402

DEFAULT_MODES = ("60-naive-light", "60-naive-heavy", "60-naive-heavy-realistic")
# The modes that also get their animation error histogram
HISTOGRAM_MODES = ("60-naive-heavy",)
WORK_DIR = gv.REPO_ROOT / "out" / "measured_charts"
SUBMODULE_PROJECT = gv.REPO_ROOT / "external" / "mb-framepacing" / "measure" / "app" / "FramePacing" / "FramePacing.csproj"
SUBMODULE_BUILD = SUBMODULE_PROJECT.parent / "bin" / "Release" / "net10.0"
# The web page's live playback report: the test clip it plays (build_blind_test.py makes its web-encoded video), and where it goes
PLAYBACK_MODE = build_blind_test.PLAYBACK_MODE
PLAYBACK_DIR = gv.REPO_ROOT / "web" / "public" / "playback" / PLAYBACK_MODE
# The timing diagrams' replay clips: the whole diagram once every second, at 60 Hz
TIMELINE_EVERY = "every-1s"
# The web page's charts' verdicts, and the letter of each (one per frame of a clip)
WEB_VERDICTS = gv.REPO_ROOT / "web" / "src" / "charts" / "verdicts.json"
VERDICTS = {
    "l": "late (Late): longer on screen than animated for, and than intended",
    "j": "delta time jitter (DeltaTimeJitter): off by less than the intended period, not late",
    "w": "an animation error within mb-framepacing's error threshold",
    "o": "another animation error",
    "-": "no animation error, or no step measured (not presented, the run's first frame, a static step)",
}
# The page's clip arguments that change a clip's frames (the others only how it looks); a marked clip takes them over
TIMING_ARGUMENTS = ("--jitter-pattern",)

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
    playback_example: bool
    timelines: bool
    web_verdicts: bool
    all: bool
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


def playback_url(page_dir: Path) -> str:
    """The path of the live playback report's video (build_blind_test.py's, in web/public/videos) relative to its page's folder."""
    return Path(os.path.relpath(build_blind_test.playback_video(build_blind_test.DEFAULT_OUTPUT_DIR), page_dir)).as_posix()


def playback_example(tool: Path, ffmpeg: Path, output_dir: Path) -> Path:
    """Import the test clip PLAYBACK_MODE with mb-framepacing's playback report, playing the video playback_url names, and copy its
    page to output_dir; returns the page."""
    settings, job = next((settings, job) for settings, job in export_test_clips.planned() if job.top.name == PLAYBACK_MODE)
    work = WORK_DIR / "playback"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    video = work / "video.mp4"
    gv.encode_video(ffmpeg, settings, job, video)
    capture = work / "capture"
    run([str(tool), "import", str(video), "-o", str(capture), "--analyze", "--playback", "--playback-video-url", playback_url(output_dir)])
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    page = output_dir / "index.html"
    _ = shutil.copyfile(capture / "analysis" / "playback" / "run-1" / "index.html", page)
    return page


def import_clip(settings: gv.Settings, job: gv.VideoJob, tool: Path, ffmpeg: Path, work: Path) -> Path:
    """Render a marked clip into `work` (emptied first) and have mb-framepacing import and analyse it; returns the capture."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    video = work / "video.mp4"
    gv.encode_video(ffmpeg, settings, job, video)
    capture = work / "capture"
    run([str(tool), "import", str(video), "-o", str(capture), "--analyze"])
    return capture


def measure_clip(settings: gv.Settings, job: gv.VideoJob, tool: Path, ffmpeg: Path, render: list[str]) -> Path:
    """Render a marked clip, have mb-framepacing import and analyse it, and draw it with the render options `render`; returns the
    folder render wrote to (out/measured_charts/<mode>/render)."""
    work = WORK_DIR / job.top.name
    capture = import_clip(settings, job, tool, ffmpeg, work)
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
    mb-framepacing's measure/test-data/videos; a title with the mode's description would run under the card's display box), without
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


def timeline_mode(name: str) -> str:
    """The replay clip of the diagram `name` its timeline card is drawn from: the whole diagram once a second."""
    return f"60-diagram-{name}-{TIMELINE_EVERY}"


def timeline_section(settings: gv.Settings, job: gv.VideoJob) -> tuple[Fraction, Fraction]:
    """The seconds of the replay clip `job` (since the run's first frame) the diagram's first copy is shown in: from its first
    refresh to half a refresh before the next copy's frames begin (render --timeline takes a frame shown at the section's end)."""
    mode = job.top
    assert mode.diagram is not None, mode.name
    refreshes = settings.frame_count(job.speed)
    interval = swap_interval(mode, settings.fps)
    _, length, offsets = diagram_replay.placement(mode.diagram, mode.every, refreshes, interval, settings.fps, mode.times)
    return offsets[0] / settings.fps, (offsets[0] + length - Fraction(1, 2)) / settings.fps


def seconds(value: Fraction) -> str:
    """A time for render --from/--to, exact to a microsecond."""
    return f"{float(value):.6f}"


def measure_timelines(names: list[str], tool: Path, ffmpeg: Path, output_dir: Path, png: bool) -> list[Path]:
    """Draw each diagram named (default: every replayable one) as mb-framepacing's frame timeline card of its replay clip:
    timeline-<name>.svg in output_dir."""
    written: list[Path] = []
    selected = names or list(diagram_replay.replayable())
    for index, name in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {name}", flush=True)
        _, settings = gv.parse_arguments(["--single", timeline_mode(name), "--marker", "--speed", "fast"])
        (job,) = gv.plan_videos(settings)
        start, end = timeline_section(settings, job)
        options = ["--timeline", "--from", seconds(start), "--to", seconds(end), *(["--png"] if png else [])]
        rendered = measure_clip(settings, job, tool, ffmpeg, options)
        for suffix in (".svg", ".png") if png else (".svg",):
            (source,) = rendered.glob(f"run-1-timeline-*{suffix}")
            path = output_dir / f"timeline-{name}{suffix}"
            _ = shutil.copyfile(source, path)
            print(path)
            written.append(path)
    return written


def page_clips() -> list[tuple[str, str]]:
    """Every clip the web page charts, as (motion, mode): the blind test's and the explanation slides' (build_blind_test.py)."""
    definitions = cast(dict[str, object], json.loads(build_blind_test.TRIALS.read_text(encoding="utf-8")))
    explanation = cast(dict[str, object], json.loads(build_blind_test.EXPLANATION_CLIPS.read_text(encoding="utf-8")))
    pairs = build_blind_test.with_explanation_clips(build_blind_test.required_pairs(definitions), explanation)
    return sorted({(motion, mode) for motion, motion_pairs in pairs.items() for pair in motion_pairs for mode in pair})


def page_timing_arguments() -> list[str]:
    """The page's clip arguments that change a clip's frames (TIMING_ARGUMENTS), with their values."""
    definitions = cast(dict[str, object], json.loads(build_blind_test.TRIALS.read_text(encoding="utf-8")))
    arguments = cast(list[str], cast(dict[str, object], definitions["clip"])["arguments"])
    return [part for at, name in enumerate(arguments) if name in TIMING_ARGUMENTS for part in arguments[at : at + 2]]


def clip_frames(settings: gv.Settings, job: gv.VideoJob) -> dict[str, object]:
    """The manifest entry of a clip's box: its mode and frames, as the video tool writes it."""
    manifest = gv.build_manifest(settings, [job])
    (video,) = cast(list[dict[str, object]], manifest["videos"])
    return video


def frame_verdicts(analysis: Path, first_index: int, count: int) -> str:
    """One letter per frame of the clip (VERDICTS) from mb-framepacing's run-1-frames.csv and summary.json; the marker's frame
    index of the clip's first frame is `first_index`."""
    threshold = cast(int, cast(dict[str, object], json.loads((analysis / "summary.json").read_text(encoding="utf-8")))["errorThresholdNs"])
    letters = ["-"] * count
    with (analysis / "run-1-frames.csv").open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            frame = int(row["frameIndex"]) - first_index
            flags = set((row.get("flags") or "").split("|"))
            error = row["animationErrorNs"]
            if not 0 <= frame < count or not error or int(error) == 0:
                continue
            letters[frame] = "l" if "Late" in flags else "j" if "DeltaTimeJitter" in flags else "w" if abs(int(error)) <= threshold else "o"
    return "".join(letters)


def measure_web_verdicts(tool: Path, ffmpeg: Path, output: Path) -> Path:
    """Measure every clip the web page charts and write their verdicts to `output`: {"key": VERDICTS, "<motion>": {"<mode>": "lj-..."}}."""
    timing = page_timing_arguments()
    clips = page_clips()
    verdicts: dict[str, dict[str, str]] = {}
    for index, (motion, mode) in enumerate(clips, start=1):
        print(f"[{index}/{len(clips)}] {motion} {mode}", flush=True)
        _, page = gv.parse_arguments(["--single", mode, "--speed", motion, *timing])
        _, settings = gv.parse_arguments(["--single", mode, "--marker", "--speed", motion, *timing])
        (page_job,), (job,) = gv.plan_videos(page), gv.plan_videos(settings)
        marked = clip_frames(settings, job)
        if cast(dict[str, object], clip_frames(page, page_job)["box"])["frames"] != cast(dict[str, object], marked["box"])["frames"]:
            raise gv.ToolError(f"{motion} {mode}: the marked clip's frames are not the page's (a timing argument missing from TIMING_ARGUMENTS?)")
        count = len(cast(list[object], cast(dict[str, object], cast(dict[str, object], marked["box"])["frames"])["refresh"]))
        capture = import_clip(settings, job, tool, ffmpeg, WORK_DIR / "web-verdicts" / motion / mode)
        verdicts.setdefault(motion, {})[mode] = frame_verdicts(capture / "analysis", cast(int, marked["markerFirstFrameIndex"]), count)
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_text(json.dumps({"key": VERDICTS, **verdicts}, indent=2) + "\n", encoding="utf-8")
    return output


def _printed(path: Path) -> Path:
    print(path)
    return path


@dataclass(frozen=True)
class Export:
    """One export to the pages: its flag, what it is (--help), whether --all makes it, and how it is made from the MODE/NAME
    arguments, mb-framepacing, FFmpeg, the output folder and --png (the files it wrote)."""

    flag: str
    help: str
    in_all: bool
    make: Callable[[list[str], Path, Path, Path, bool], list[Path]]


EXPORTS = (
    Export(
        "test-clips",
        "measure the test clips (MODE: some of them; default all) as test-clip-<mode>.svg, the default report card",
        True,
        lambda modes, tool, ffmpeg, output_dir, png: measure_test_clips(modes, tool, ffmpeg, output_dir, png),
    ),
    Export(
        "playback-example",
        f"write the web page's live playback report of {PLAYBACK_MODE} to {PLAYBACK_DIR.relative_to(gv.REPO_ROOT).as_posix()}",
        True,
        lambda _modes, tool, ffmpeg, _output_dir, _png: [_printed(playback_example(tool, ffmpeg, PLAYBACK_DIR))],
    ),
    Export(
        "timelines",
        "draw the timing diagrams (NAME: some of them; default every replayable one) as mb-framepacing's frame timeline card, timeline-<name>.svg",
        False,
        lambda names, tool, ffmpeg, output_dir, png: measure_timelines(names, tool, ffmpeg, output_dir, png),
    ),
    Export(
        "web-verdicts",
        f"measure every clip the web page charts and write each frame's verdict to {WEB_VERDICTS.relative_to(gv.REPO_ROOT).as_posix()}",
        True,
        lambda _modes, tool, ffmpeg, _output_dir, _png: [_printed(measure_web_verdicts(tool, ffmpeg, WEB_VERDICTS))],
    ),
)


def report_cards(modes: list[str], tool: Path, ffmpeg: Path, output_dir: Path, png: bool) -> list[Path]:
    """The report cards of doc/charts.md: each mode's (default DEFAULT_MODES)."""
    selected = modes or list(DEFAULT_MODES)
    written: list[Path] = []
    for index, mode in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {mode}", flush=True)
        for path in measure(mode, tool, ffmpeg, output_dir, png):
            print(path)
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate everything this repository takes from mb-framepacing: its charts and verdicts of the clips.")
    _ = parser.add_argument(
        "modes", nargs="*", metavar="MODE", help=f"report cards: video modes to measure (default: {', '.join(DEFAULT_MODES)}); with an export, what it takes"
    )
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the cards go (default: doc/images)")
    _ = parser.add_argument("--png", action="store_true", help="also save a PNG at 2x of each, through a headless Edge or Chrome")
    for export in EXPORTS:
        _ = parser.add_argument(f"--{export.flag}", action="store_true", help=export.help)
    _ = parser.add_argument(
        "--all", action="store_true", help="the report cards and every export the pages use (" + ", ".join(e.flag for e in EXPORTS if e.in_all) + ")"
    )
    _ = parser.add_argument(
        "--mb-framepacing", metavar="PATH", help="mb-framepacing executable or its folder (default: MB_FRAMEPACING, local.toml, then the submodule's, built)"
    )
    _ = parser.add_argument("--ffmpeg", metavar="PATH", help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    _ = parser.add_argument("--config", type=Path, metavar="FILE", help="machine-local settings file (default: local.toml in the repository root)")
    args = parser.parse_args(argv, namespace=Arguments())
    named = [export for export in EXPORTS if getattr(args, export.flag.replace("-", "_"))]
    if args.all and (named or args.modes):
        parser.error("--all makes everything: name no export and no MODE with it")
    if len(named) > 1 and args.modes:
        parser.error("MODE/NAME arguments go with one export at a time")
    if any(export.flag == "test-clips" for export in named):
        unknown = [mode for mode in args.modes if mode not in export_test_clips.SCENARIOS]
        if unknown:
            parser.error(f"not a test clip: {', '.join(unknown)} (the test clips are export_test_clips.SCENARIOS)")
    elif any(export.flag == "timelines" for export in named):
        unknown = [name for name in args.modes if name not in diagram_replay.replayable()]
        if unknown:
            parser.error(f"not a replayable diagram: {', '.join(unknown)} (use one of {', '.join(diagram_replay.replayable())})")
    else:
        for mode in args.modes:
            try:
                _ = parse_mode(mode)
            except ValueError as error:
                parser.error(str(error))
    try:
        tool = find_mb_framepacing(args.mb_framepacing, args.config)
        ffmpeg = gv.find_ffmpeg(args.ffmpeg, args.config).path
        gv.require_lossless_encoder(gv.list_encoders(ffmpeg), ffmpeg)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.all or not named:
            _ = report_cards(args.modes, tool, ffmpeg, args.output_dir, args.png)
        for export in [export for export in EXPORTS if export.in_all] if args.all else named:
            print(f"--{export.flag}", flush=True)
            _ = export.make(args.modes, tool, ffmpeg, args.output_dir, args.png)
    except (gv.ToolError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
