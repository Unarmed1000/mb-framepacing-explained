#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate exactly the clips the web page needs, web-encoded, into web/public/videos: the blind test's and the explanation slides'.

The questions live in web/src/blind-test/trials.json, the one place both the page and this script read. For every motion (a
speed of the single-box scene; never the rows) it collects the top/bottom pairs: identical pairs once, every other pair in both
orders (the page asks each pair once with each mode on top), plus the warm-up pairs for the warm-up's motions. It runs the video
tool once per motion, so each motion's folder (videos/box/<motion>) gets all its clips and one complete manifest.json, and renders
the slides' rendered videos (clips.json's "rendered", e.g. the dynamic resolution example) into videos/rendered, and the video of
the live playback report (PLAYBACK_MODE, marked, into videos/box-single-marker; the report is generate_measured_charts.py's). Every command
writes its own files, so they run side by side (--jobs, default one per CPU core); each one's output is printed when it ends.

Run from the repository's .venv:
  python tools/web_export/build_blind_test.py [--output-dir DIR] [--ffmpeg PATH] [--jobs N]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIALS = REPO_ROOT / "web" / "src" / "blind-test" / "trials.json"
# The explanation slides' clips, top and bottom mode of each, in one motion
EXPLANATION_CLIPS = REPO_ROOT / "web" / "src" / "explain" / "clips.json"
GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_videos.py"
# The slides' rendered videos (3D scenes, OpenGL): not clips of the video tool
RENDER_GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_render_scale_video.py"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "web" / "public" / "videos"
# The web page's live playback report (generate_measured_charts.py --playback-example) plays this test clip, web-encoded: the same
# frames and timestamps as the clip mb-framepacing imported for it, only encoded for browsers
PLAYBACK_MODE = "60-busy-adaptive"
PLAYBACK_SPEED = "fast"


def required_pairs(definitions: dict[str, object]) -> dict[str, list[tuple[str, str]]]:
    """Per motion, every top/bottom pair the test needs (each trial in its own movements): identical pairs once, the others in
    both orders, first seen first."""
    pairs: dict[str, dict[tuple[str, str], None]] = {}

    def add(motion: str, a: str, b: str) -> None:
        motion_pairs = pairs.setdefault(motion, {})
        motion_pairs[(a, b)] = None
        motion_pairs[(b, a)] = None

    trials = cast(list[dict[str, object]], definitions["trials"])
    for trial in trials:
        # A trial may limit its movements (20 Hz is only shown with the slower movement); default: all of the test's
        for motion in cast(list[str], trial.get("motions", definitions["motions"])):
            add(motion, str(trial["a"]), str(trial["b"]))
    # The test-wide warm-up, and the tests' own
    warmups = [cast(dict[str, object], definitions["warmup"])]
    warmups += [
        cast(dict[str, object], test["warmup"]) for test in cast(list[dict[str, object]], definitions.get("tests", [])) if isinstance(test.get("warmup"), dict)
    ]
    for warmup in warmups:
        for motion in cast(list[str], warmup["motions"]):
            for a, b in cast(list[list[str]], warmup["pairs"]):
                add(motion, a, b)
    return {motion: list(motion_pairs) for motion, motion_pairs in pairs.items()}


def with_explanation_clips(pairs: dict[str, list[tuple[str, str]]], clips: dict[str, object]) -> dict[str, list[tuple[str, str]]]:
    """The blind test's pairs plus the explanation slides' clips (in their motion, each pair as listed, none twice)."""
    motion = str(clips["motion"])
    merged = {name: list(motion_pairs) for name, motion_pairs in pairs.items()}
    extra = [(top, bottom) for top, bottom in cast(list[list[str]], clips["pairs"])]
    merged[motion] = list(dict.fromkeys([*merged.get(motion, []), *extra]))
    return merged


def generator_command(motion: str, pairs: list[tuple[str, str]], clip_arguments: list[str], output_dir: Path, ffmpeg: str | None) -> list[str]:
    command = [sys.executable, str(GENERATOR), *clip_arguments, "--speed", motion, "--output-dir", str(output_dir), "--pairs"]
    command += [f"{top}:{bottom}" for top, bottom in pairs]
    return command + (["--ffmpeg", ffmpeg] if ffmpeg else [])


def rendered_commands(clips: dict[str, object], output_dir: Path, ffmpeg: str | None) -> list[list[str]]:
    """The command for each of clips.json's rendered videos: its generator (RENDER_GENERATOR, or another script next to it named
    by `generator`) with its arguments, into videos/rendered/<name>.mp4."""
    commands: list[list[str]] = []
    for video in cast(list[dict[str, object]], clips.get("rendered", [])):
        output = output_dir / "rendered" / f"{video['name']}.mp4"
        generator = RENDER_GENERATOR.parent / cast(str, video.get("generator", RENDER_GENERATOR.name))
        command = [sys.executable, str(generator), *cast(list[str], video["arguments"]), "--output", str(output)]
        commands.append(command + (["--ffmpeg", ffmpeg] if ffmpeg else []))
    return commands


def playback_command(output_dir: Path, ffmpeg: str | None) -> list[str]:
    """The command for the live playback report's video: the test clip PLAYBACK_MODE, marked and web-encoded (playback_video)."""
    command = [sys.executable, str(GENERATOR), "--single", PLAYBACK_MODE, "--marker", "--web", "--speed", PLAYBACK_SPEED, "--output-dir", str(output_dir)]
    return command + (["--ffmpeg", ffmpeg] if ffmpeg else [])


def playback_video(output_dir: Path) -> Path:
    """Where playback_command writes the live playback report's video (the video tool's folder and name for a marked clip)."""
    return output_dir / "box-single-marker" / PLAYBACK_SPEED / f"single_{PLAYBACK_SPEED}_{PLAYBACK_MODE}.mp4"


@dataclass(frozen=True)
class Step:
    """One command of the build, and what to call it."""

    name: str
    command: list[str]


@dataclass(frozen=True)
class Outcome:
    """How a step ended: its exit code, its output (stdout and stderr) and how long it took, in seconds."""

    step: Step
    returncode: int
    output: str
    seconds: float


def run_step(step: Step) -> Outcome:
    """Run a step to its end, keeping its output (so steps running side by side do not mix theirs)."""
    start = time.monotonic()
    result = subprocess.run(step.command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return Outcome(step, result.returncode, result.stdout + result.stderr, time.monotonic() - start)


def run_steps(steps: Sequence[Step], jobs: int) -> list[Outcome]:
    """Run the steps, `jobs` at a time, started in the order listed (the longest first), printing each one as it ends (a failed
    one with its output). Every step runs, whether others failed or not; the outcomes come back in the order listed."""
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_step, step) for step in steps]
        for future in as_completed(futures):
            outcome = future.result()
            status = "done" if outcome.returncode == 0 else f"FAILED (exit code {outcome.returncode})"
            print(f"{outcome.step.name}: {status} in {outcome.seconds:.0f} s", flush=True)
            if outcome.returncode != 0:
                print(outcome.output.rstrip(), flush=True)
    return [future.result() for future in futures]


class Arguments(argparse.Namespace):
    output_dir: Path
    ffmpeg: str | None
    jobs: int


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the blind test's clips (web-encoded) for the web page.")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the clips go (default: web/public/videos)")
    _ = parser.add_argument("--ffmpeg", default=None, help="FFmpeg executable or its folder (default: as the video tool finds it)")
    _ = parser.add_argument(
        "--jobs", type=int, default=os.process_cpu_count() or 1, help="how many commands run side by side (default: one per CPU core; 1: one after another)"
    )
    args = parser.parse_args(argv, namespace=Arguments())
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    definitions = cast(dict[str, object], json.loads(TRIALS.read_text(encoding="utf-8")))
    clip_arguments = cast(list[str], cast(dict[str, object], definitions["clip"])["arguments"])
    clips = cast(dict[str, object], json.loads(EXPLANATION_CLIPS.read_text(encoding="utf-8")))
    steps: list[Step] = []
    for motion, pairs in with_explanation_clips(required_pairs(definitions), clips).items():
        if motion.startswith("ui"):
            parser.error(f"{TRIALS.name} asks for {motion}: the blind test never uses the rows (ui scroll)")
        bad_pairs = [f"{top}:{bottom}" for top, bottom in pairs if "naive" in top and "naive" in bottom]
        if bad_pairs:
            parser.error(f"{TRIALS.name} compares two bad timers ({', '.join(bad_pairs)}): the blind test never does")
        steps.append(Step(f"{motion}: {len(pairs)} clips", generator_command(motion, pairs, clip_arguments, args.output_dir, args.ffmpeg)))
    for command in rendered_commands(clips, args.output_dir, args.ffmpeg):
        steps.append(Step(f"rendered: {Path(command[command.index('--output') + 1]).name}", command))
    steps.append(Step(f"playback report's video: {PLAYBACK_MODE}", playback_command(args.output_dir, args.ffmpeg)))
    print(f"{len(steps)} commands, {args.jobs} at a time", flush=True)
    failed = [outcome for outcome in run_steps(steps, args.jobs) if outcome.returncode != 0]
    if failed:
        print(f"error: {len(failed)} of {len(steps)} commands failed: {', '.join(outcome.step.name for outcome in failed)}", file=sys.stderr)
        return failed[0].returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
