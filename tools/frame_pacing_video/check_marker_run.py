#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Compare mb-framepacing's measurement of a marked clip (generate_videos.py --single ... --marker) with what the generator made.

Import the clip with mb-framepacing first, as its manifest entry says ("measure"), for example:
  mb-framepacing import single_fast_60-naive-5ms.mp4 --analyze -o single_fast_60-naive-5ms
then point this script at the manifest, the clip's file name and the analysis folder:
  python tools/frame_pacing_video/check_marker_run.py manifest.json single_fast_60-naive-5ms.mp4 single_fast_60-naive-5ms/analysis

It reads mb-framepacing's run-1-frames.csv and checks, frame by frame, that every frame the clip presents was presented and that its
animation error is the manifest's (animationErrorMs), within --tolerance-ms. A clip with a presentation fault (-dropped-frames,
-out-of-order, -dropped-before-wake, -dropped-wake) lists the frames it presents (presented); the others must not be measured. The run's first frame
has no error in mb-framepacing (no previous frame), and neither has the step from a static frame to the next (an idle behaviour's
frames at rest: the manifest's staticAfter on the frame, or staticBefore on the next frame when that is frame index + 1), so those are
not compared; the step into a static frame is. Exit code 0 when they agree.
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


def expected_errors(manifest: Path, video: str) -> tuple[int, list[float | None], list[int] | None]:
    """The marker frame index of the clip's first frame, the animation error of every frame of the clip (None: not presented) and,
    with a presentation fault, the frames the clip presents (None: every frame), from the manifest."""
    data = cast(dict[str, object], json.loads(manifest.read_text(encoding="utf-8")))
    videos = cast(list[dict[str, object]], data["videos"])
    entry = next((item for item in videos if item["file"] == video), None)
    if entry is None:
        raise ValueError(f"{video} is not in {manifest}")
    if "markerFirstFrameIndex" not in entry:
        raise ValueError(f"{video} has no marker: make it with generate_videos.py --single ... --marker")
    box = cast(dict[str, object], entry["box"])
    frames = cast(dict[str, object], box["frames"])
    errors = cast(list[float | None], frames["animationErrorMs"])
    presented = cast(list[int] | None, box.get("presented"))
    after = cast(list[bool] | None, frames.get("staticAfter"))
    before = cast(list[bool] | None, frames.get("staticBefore"))
    if after is not None and before is not None:
        order = presented if presented is not None else list(range(len(errors)))
        for position, index in enumerate(order):
            if static_step(after, before, order[position - 1], index):
                errors[index] = None
    return cast(int, entry["markerFirstFrameIndex"]), errors, presented


def static_step(after: Sequence[bool], before: Sequence[bool], previous: int, index: int) -> bool:
    """Whether mb-framepacing leaves the step from presented frame `previous` to presented frame `index` unjudged: the previous frame
    is static after, or this one is static before and follows it directly (frame index - 1; the clip's first frame follows its last
    one, the previous loop's). Static before after a frame never shown marks nothing."""
    follows = previous == index - 1 or (index == 0 and previous == len(before) - 1)
    return after[previous] or (before[index] and follows)


def measured_errors(analysis: Path) -> dict[int, float | None]:
    """mb-framepacing's animation error of every presented frame of run 1, by marker frame index (None for the run's first frame)."""
    with (analysis / "run-1-frames.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    return {int(row["frameIndex"]): float(row["animationErrorMs"]) if row["animationErrorMs"] else None for row in rows}


def compare(
    first_index: int, expected: list[float | None], measured: dict[int, float | None], tolerance_ms: float, presented: Sequence[int] | None = None
) -> list[str]:
    """What disagrees: frames the clip presents missing from the measurement, frames the clip does not have, frames it has but does
    not present (a presentation fault) found in the measurement, and errors further apart than the tolerance."""
    problems: list[str] = []
    indices = range(first_index, first_index + len(expected))
    shown = set(indices) if presented is None else {first_index + offset for offset in presented}
    missing = sorted(shown - set(measured))
    if missing:
        problems.append(f"{len(missing)} frame(s) not presented in the measurement, first {missing[0]}")
    extra = sorted(set(measured) - set(indices))
    if extra:
        problems.append(f"{len(extra)} frame(s) the clip does not have, first {extra[0]}")
    unexpected = sorted((set(indices) - shown) & set(measured))
    if unexpected:
        problems.append(f"{len(unexpected)} frame(s) the clip does not present, first {unexpected[0]}")
    for offset, error in enumerate(expected):
        value = measured.get(first_index + offset)
        if value is not None and error is not None and abs(value - error) > tolerance_ms:
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
        first_index, expected, presented = expected_errors(args.manifest, args.video)
        measured = measured_errors(args.analysis)
    except (OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    problems = compare(first_index, expected, measured, args.tolerance_ms, presented)
    compared = sum(1 for offset in range(len(expected)) if measured.get(first_index + offset) is not None)
    if problems:
        print(f"{args.video}: {len(problems)} difference(s) in {len(expected)} frames")
        for problem in problems[:20]:
            print(f"  {problem}")
        return 1
    absent = 0 if presented is None else len(expected) - len(presented)
    shown = (
        f"all {len(expected)} frames presented" if absent == 0 else f"{len(expected) - absent} of {len(expected)} frames presented as expected ({absent} not)"
    )
    print(f"{args.video}: {shown}, {compared} animation errors equal within {args.tolerance_ms} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
