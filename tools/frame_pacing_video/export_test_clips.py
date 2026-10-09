#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Export the web page's scenarios as marked single-box clips for mb-framepacing's tests (its measure/test-data/videos): one folder per
scenario, named after its mode, holding video.mp4 and its own manifest.json.

  python tools/frame_pacing_video/export_test_clips.py --output-dir <mb-framepacing>/measure/test-data/videos

Each clip is generate_videos.py --single MODE --marker --speed fast: lossless, 1280 x 720, 8 s plus 3 refreshes of start marker
before and 3 of end marker after. Its manifest is the generator's, for that one clip: per frame the refresh it is flipped on, its
animation error, how late it is, the rate the game aims for (targetFps), its CPU start time and CPU busy (cpuStartNs, cpuBusyNs),
the marker frame index of the clip's first frame and the start marker's sequence id.
Two clips add a presentation fault to the perfect storm (presentation_faults.py): dropped frames (runs of 1 to 4 rendered frames
never shown) and frames out of order (swapped pairs, and blocks of 3 and 4 in an order where no frame keeps its place). Their
manifests also give the frame on screen in every refresh (screen), the frames a measurement counts as presented (presented), the
fault events (fault) and the counts a measurement should find (expected); a frame that is not presented has no animation error.
Four clips show what a game does while nothing moves (idle_behaviour.py), for the marker's static flags and preferred frame time: the
naive timer with its frames at rest flagged static, a renderer that presents on demand (its clock running on, or paused while idle),
and a device idling at 1 fps (at the idle speed, whose rests are 3 s: SCENARIO_SPEEDS). Three more set the static flags each way a
game can: a rest rendered every refresh with its clock paused (static after, and inside the rest static before too); the on-demand
renderer with the paused clock flagged in hindsight (static before on the frame that wakes up, which analyses like the paused clock's
static after on the frame before the wait); the same with a rest's frame dropped, so the static before after it marks nothing; and
with the frame that wakes up dropped, so its static before never reaches the screen and, by the flags alone, the rest is judged.
Three more are for mb-framepacing's guess of such a lost rest (it assumes the frame that held the rest static): the paused clock's static after lost with its dropped rest frame; and two that are no
rest, frames dropped in the middle of the motion, and a stall of a rest's length (the clock running on) with the frame after it
dropped. Their manifests give each frame's staticAfter and staticBefore, and with a fault the steps static by those flags
(expected.staticSteps).
The copies made for mb-framepacing are licensed for it under its PolyForm Perimeter License 1.0.1, like the rest of its tools' test
data (the manifest's "license"); this repository's own videos stay CC BY-NC-SA 4.0.
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import generate_videos as gv

# The web page's scenarios: the perfect timer at full and half rate, delta time jitter, late frames, half rate evenly and badly
# paced, a busy stretch at full rate and adapting like the Swappy frame pacer, and the perfect storm (jitter and late frames at once); then the
# perfect storm with dropped frames and with frames out of order, for mb-framepacing's skipped and out of order frames; what a game
# does while nothing moves, for the marker's static flags and preferred frame time; and the static flags set each way: both inside a
# rest, in hindsight, in hindsight after a frame never shown, and in hindsight on a frame never shown; then a static after lost
# with its frame, and the look-alikes that are no rest: frames dropped in the motion, and a frame dropped after a stall
SCENARIOS = (
    "60",
    "30",
    "60-naive-5ms",
    "60-diagram-slow-frames-every-1s",
    "60-diagram-half-rate-even",
    "60-diagram-half-rate-bad-pacing",
    "60-busy-full-rate",
    "60-busy-adaptive",
    "60-naive-5ms-diagram-slow-frames-every-1s",
    "60-naive-5ms-diagram-slow-frames-every-1s-dropped-frames",
    "60-naive-5ms-diagram-slow-frames-every-1s-out-of-order",
    "60-naive-5ms-static-rests",
    "60-on-demand",
    "60-on-demand-paused-clock",
    "60-idle-1fps",
    "60-static-rests-paused-clock",
    "60-on-demand-paused-clock-hindsight",
    "60-on-demand-paused-clock-hindsight-dropped-before-wake",
    "60-on-demand-paused-clock-hindsight-dropped-wake",
    "60-on-demand-paused-clock-dropped-before-wake",
    "60-on-demand-paused-clock-hindsight-dropped-frames",
    "60-on-demand-paused-clock-hindsight-dropped-after-stall",
)
# The speed of each scenario: fast, unless it needs the idle speed's long rests
DEFAULT_SPEED = "fast"
SCENARIO_SPEEDS = {"60-idle-1fps": "idle"}
VIDEO_NAME = "video.mp4"
# The license of the copies in mb-framepacing's measure/test-data/videos, as its README says, so they can be copied there unchanged
TEST_DATA_LICENSE = "PolyForm Perimeter License 1.0.1 (mb-framepacing LICENSE), (c) 2026 Mana Battery ApS; made by mb-framepacing-explained"


class Arguments(argparse.Namespace):
    output_dir: Path
    ffmpeg: str | None
    config: Path | None


def clip_manifest(settings: gv.Settings, job: gv.VideoJob) -> dict[str, object]:
    """The generator's manifest for one clip, renamed to the folder's video.mp4, under mb-framepacing's license."""
    manifest = gv.build_manifest(settings, [job])
    manifest["license"] = TEST_DATA_LICENSE
    video = cast(list[dict[str, object]], manifest["videos"])[0]
    video["file"] = VIDEO_NAME
    video["measure"] = f"mb-framepacing import {VIDEO_NAME} --analyze -o analysis"
    return manifest


def planned() -> list[tuple[gv.Settings, gv.VideoJob]]:
    """Every scenario's marked single-box clip, in SCENARIOS order, each at its speed."""
    by_speed: dict[str, list[str]] = {}
    for mode in SCENARIOS:
        by_speed.setdefault(SCENARIO_SPEEDS.get(mode, DEFAULT_SPEED), []).append(mode)
    clips: dict[str, tuple[gv.Settings, gv.VideoJob]] = {}
    for speed, modes in by_speed.items():
        _, settings = gv.parse_arguments(["--single", *modes, "--marker", "--speed", speed])
        clips.update((job.top.name, (settings, job)) for job in gv.plan_videos(settings))
    return [clips[mode] for mode in SCENARIOS]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the scenarios as marked single-box clips, a folder each, for mb-framepacing's tests.")
    _ = parser.add_argument("--output-dir", type=Path, required=True, help="folder to write a folder per scenario into")
    _ = parser.add_argument("--ffmpeg", metavar="PATH", help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    _ = parser.add_argument("--config", type=Path, metavar="FILE", help="machine-local settings file (default: local.toml in the repository root)")
    args = parser.parse_args(argv, namespace=Arguments())
    clips = planned()
    try:
        location = gv.find_ffmpeg(args.ffmpeg, args.config)
        gv.require_lossless_encoder(gv.list_encoders(location.path), location.path)
        for index, (settings, job) in enumerate(clips, start=1):
            folder = args.output_dir / job.top.name
            folder.mkdir(parents=True, exist_ok=True)
            print(f"[{index}/{len(clips)}] {job.top.name}/{VIDEO_NAME}", flush=True)
            gv.encode_video(location.path, settings, job, folder / VIDEO_NAME)
            _ = (folder / gv.MANIFEST_NAME).write_text(json.dumps(clip_manifest(settings, job), indent=2) + "\n", encoding="utf-8")
    except (gv.FfmpegError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Done: {len(clips)} clips in {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
