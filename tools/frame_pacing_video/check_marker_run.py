#!/usr/bin/env python3
"""Compare mb-framepacing's measurement of a marked clip (generate_videos.py --single ... --marker) with what the generator made.

Import the clip with mb-framepacing first, as its manifest entry says ("measure"), for example:
  mb-framepacing import single_fast_60-naive-5ms.mp4 --analyze -o single_fast_60-naive-5ms
then point this script at the manifest, the clip's file name and the analysis folder:
  python tools/frame_pacing_video/check_marker_run.py manifest.json single_fast_60-naive-5ms.mp4 single_fast_60-naive-5ms/analysis

It reads mb-framepacing's run-1-frames.csv and checks, frame by frame, that every frame of the clip was presented and that its
animation error is the manifest's (animationErrorMs), within --tolerance-ms. The run's first frame has no error in mb-framepacing (no
previous frame), so it is not compared. Exit code 0 when they agree.
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

# The manifest keeps 3 decimals (ms) and mb-framepacing 4; the capture times come from the video's timestamps
DEFAULT_TOLERANCE_MS = 0.01


class Arguments(argparse.Namespace):
    manifest: Path
    video: str
    analysis: Path
    tolerance_ms: float


def expected_errors(manifest: Path, video: str) -> tuple[int, list[float]]:
    """The marker frame index of the clip's first frame and the animation error of every frame of the clip, from the manifest."""
    data = cast(dict[str, object], json.loads(manifest.read_text(encoding="utf-8")))
    videos = cast(list[dict[str, object]], data["videos"])
    entry = next((item for item in videos if item["file"] == video), None)
    if entry is None:
        raise ValueError(f"{video} is not in {manifest}")
    if "markerFirstFrameIndex" not in entry:
        raise ValueError(f"{video} has no marker: make it with generate_videos.py --single ... --marker")
    frames = cast(dict[str, object], cast(dict[str, object], entry["box"])["frames"])
    return cast(int, entry["markerFirstFrameIndex"]), cast(list[float], frames["animationErrorMs"])


def measured_errors(analysis: Path) -> dict[int, float | None]:
    """mb-framepacing's animation error of every presented frame of run 1, by marker frame index (None for the run's first frame)."""
    with (analysis / "run-1-frames.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    return {int(row["frameIndex"]): float(row["animationErrorMs"]) if row["animationErrorMs"] else None for row in rows}


def compare(first_index: int, expected: list[float], measured: dict[int, float | None], tolerance_ms: float) -> list[str]:
    """What disagrees: frames missing from the measurement, frames the clip does not have, and errors further apart than the
    tolerance."""
    problems: list[str] = []
    indices = range(first_index, first_index + len(expected))
    missing = [index for index in indices if index not in measured]
    if missing:
        problems.append(f"{len(missing)} frame(s) not presented in the measurement, first {missing[0]}")
    extra = sorted(set(measured) - set(indices))
    if extra:
        problems.append(f"{len(extra)} frame(s) the clip does not have, first {extra[0]}")
    for offset, error in enumerate(expected):
        value = measured.get(first_index + offset)
        if value is not None and abs(value - error) > tolerance_ms:
            problems.append(f"frame {offset} (index {first_index + offset}): measured {value} ms, expected {error} ms")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare mb-framepacing's measurement of a marked clip with the generator's manifest.")
    _ = parser.add_argument("manifest", type=Path, help="the clip folder's manifest.json")
    _ = parser.add_argument("video", help="the clip's file name, as in the manifest")
    _ = parser.add_argument("analysis", type=Path, help="mb-framepacing's analysis folder of the clip (it holds run-1-frames.csv)")
    _ = parser.add_argument("--tolerance-ms", type=float, default=DEFAULT_TOLERANCE_MS, help="largest difference in animation error that counts as equal")
    args = parser.parse_args(argv, namespace=Arguments())
    try:
        first_index, expected = expected_errors(args.manifest, args.video)
        measured = measured_errors(args.analysis)
    except (OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    problems = compare(first_index, expected, measured, args.tolerance_ms)
    compared = sum(1 for offset in range(len(expected)) if measured.get(first_index + offset) is not None)
    if problems:
        print(f"{args.video}: {len(problems)} difference(s) in {len(expected)} frames")
        for problem in problems[:20]:
            print(f"  {problem}")
        return 1
    print(f"{args.video}: all {len(expected)} frames presented, {compared} animation errors equal within {args.tolerance_ms} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
