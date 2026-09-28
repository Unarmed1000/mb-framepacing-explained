#!/usr/bin/env python3
"""Export the web page's scenarios as marked single-box clips for mb-framepacing's tests (its test-data/videos): one folder per
scenario, named after its mode, holding video.mp4 and its own manifest.json.

  python tools/frame_pacing_video/export_test_clips.py --output-dir <mb-framepacing>/test-data/videos

Each clip is generate_videos.py --single MODE --marker --speed fast: lossless, 1280 x 720, 8 s plus 3 refreshes of start marker
before and 3 of end marker after. Its manifest is the generator's, for that one clip: per frame the refresh it is flipped on, its
animation error, how late it is, the rate the game aims for (targetFps), its CPU start time and CPU busy (cpuStartTicks, cpuBusyTicks),
the marker frame index of the clip's first frame and the start marker's sequence id.
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
# paced, a busy stretch at full rate and adapting like Swappy, and the perfect storm (jitter and late frames at once)
SCENARIOS = (
    "60",
    "30",
    "60-naive-5ms",
    "60-diagram-slow-frames-every-1s",
    "60-diagram-half-rate-even",
    "60-diagram-half-rate-bad-pacing",
    "60-busy-full-rate",
    "60-busy-swappy",
    "60-naive-5ms-diagram-slow-frames-every-1s",
)
VIDEO_NAME = "video.mp4"
# The license of the copies in mb-framepacing's test-data/videos, as its README says, so they can be copied there unchanged
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the scenarios as marked single-box clips, a folder each, for mb-framepacing's tests.")
    _ = parser.add_argument("--output-dir", type=Path, required=True, help="folder to write a folder per scenario into")
    _ = parser.add_argument("--ffmpeg", metavar="PATH", help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    _ = parser.add_argument("--config", type=Path, metavar="FILE", help="machine-local settings file (default: local.toml in the repository root)")
    args = parser.parse_args(argv, namespace=Arguments())
    _, settings = gv.parse_arguments(["--single", *SCENARIOS, "--marker", "--speed", "fast"])
    try:
        location = gv.find_ffmpeg(args.ffmpeg, args.config)
        gv.require_lossless_encoder(gv.list_encoders(location.path), location.path)
        jobs = gv.plan_videos(settings)
        for index, job in enumerate(jobs, start=1):
            folder = args.output_dir / job.top.name
            folder.mkdir(parents=True, exist_ok=True)
            print(f"[{index}/{len(jobs)}] {job.top.name}/{VIDEO_NAME}", flush=True)
            gv.encode_video(location.path, settings, job, folder / VIDEO_NAME)
            _ = (folder / gv.MANIFEST_NAME).write_text(json.dumps(clip_manifest(settings, job), indent=2) + "\n", encoding="utf-8")
    except (gv.FfmpegError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Done: {len(jobs)} clips in {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
