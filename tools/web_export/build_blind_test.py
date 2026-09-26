#!/usr/bin/env python3
"""Generate exactly the clips the web page's blind test needs, web-encoded, into web/public/videos.

The questions live in web/src/blind-test/trials.json, the one place both the page and this script read. For every motion (a
speed of the single-box scene; never the rows) it collects the top/bottom pairs: identical pairs once, every other pair in both
orders (the page asks each pair once with each mode on top), plus the warm-up pairs for the warm-up's motions. Then it runs the video
tool once per motion, so each motion's folder (videos/box/<motion>) gets all its clips and one complete manifest.json.

Run from the repository's .venv:
  python tools/web_export/build_blind_test.py [--output-dir DIR] [--ffmpeg PATH]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIALS = REPO_ROOT / "web" / "src" / "blind-test" / "trials.json"
GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_videos.py"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "web" / "public" / "videos"


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
    warmup = cast(dict[str, object], definitions["warmup"])
    for motion in cast(list[str], warmup["motions"]):
        for a, b in cast(list[list[str]], warmup["pairs"]):
            add(motion, a, b)
    return {motion: list(motion_pairs) for motion, motion_pairs in pairs.items()}


def generator_command(motion: str, pairs: list[tuple[str, str]], clip_arguments: list[str], output_dir: Path, ffmpeg: str | None) -> list[str]:
    command = [sys.executable, str(GENERATOR), *clip_arguments, "--speed", motion, "--output-dir", str(output_dir), "--pairs"]
    command += [f"{top}:{bottom}" for top, bottom in pairs]
    return command + (["--ffmpeg", ffmpeg] if ffmpeg else [])


class Arguments(argparse.Namespace):
    output_dir: Path
    ffmpeg: str | None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the blind test's clips (web-encoded) for the web page.")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="where the clips go (default: web/public/videos)")
    _ = parser.add_argument("--ffmpeg", default=None, help="FFmpeg executable or its folder (default: as the video tool finds it)")
    args = parser.parse_args(argv, namespace=Arguments())
    definitions = cast(dict[str, object], json.loads(TRIALS.read_text(encoding="utf-8")))
    clip_arguments = cast(list[str], cast(dict[str, object], definitions["clip"])["arguments"])
    for motion, pairs in required_pairs(definitions).items():
        if motion.startswith("ui"):
            parser.error(f"{TRIALS.name} asks for {motion}: the blind test never uses the rows (ui scroll)")
        bad_pairs = [f"{top}:{bottom}" for top, bottom in pairs if "naive" in top and "naive" in bottom]
        if bad_pairs:
            parser.error(f"{TRIALS.name} compares two bad timers ({', '.join(bad_pairs)}): the blind test never does")
        print(f"{motion}: {len(pairs)} clips", flush=True)
        result = subprocess.run(generator_command(motion, pairs, clip_arguments, args.output_dir, args.ffmpeg), check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
