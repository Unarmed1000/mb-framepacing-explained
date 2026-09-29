#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Make exactly one video of generate_videos.py into a given file: for the web page's rendered videos (web/src/explain/clips.json,
whose generators write one file with --output).

  python tools/frame_pacing_video/generate_one_video.py [generate_videos.py options] --output FILE

The options are generate_videos.py's (--ffmpeg and --config included) and must select exactly one video, for example the follow
camera with one stack of boxes: --scene follow --follow-boxes 60 60-naive-1ms --labels --web.
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import generate_videos as gv


class Arguments(argparse.Namespace):
    output: Path


def one_job(argv: Sequence[str]) -> tuple[gv.Arguments, gv.Settings, gv.VideoJob]:
    """The generator's command line, its settings and its one video. Raises ValueError unless the options select exactly one."""
    args, settings = gv.parse_arguments(argv)
    jobs = gv.plan_videos(settings)
    if len(jobs) != 1:
        raise ValueError(f"the options select {len(jobs)} videos; select one (one speed, one pair, stack or mode)")
    return args, settings, jobs[0]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make one video of generate_videos.py into a file.", add_help=False)
    _ = parser.add_argument("--output", type=Path, required=True, help="the video file")
    known, rest = parser.parse_known_args(argv, namespace=Arguments())
    output = known.output
    try:
        args, settings, job = one_job(rest)
        location = gv.find_ffmpeg(args.ffmpeg, args.config)
        gv.require_lossless_encoder(gv.list_encoders(location.path), location.path)
        output.parent.mkdir(parents=True, exist_ok=True)
        gv.encode_video(location.path, settings, job, output)
    except (ValueError, gv.FfmpegError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{output}: {settings.video_frame_count(job)} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
