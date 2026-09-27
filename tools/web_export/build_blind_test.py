#!/usr/bin/env python3
"""Generate exactly the clips the web page needs, web-encoded, into web/public/videos: the blind test's and the explanation slides'.

The questions live in web/src/blind-test/trials.json, the one place both the page and this script read. For every motion (a
speed of the single-box scene; never the rows) it collects the top/bottom pairs: identical pairs once, every other pair in both
orders (the page asks each pair once with each mode on top), plus the warm-up pairs for the warm-up's motions. Then it runs the video
tool once per motion, so each motion's folder (videos/box/<motion>) gets all its clips and one complete manifest.json. Last, it
renders the slides' rendered videos (clips.json's "rendered", e.g. the dynamic resolution example) into videos/rendered.

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
# The explanation slides' clips, top and bottom mode of each, in one motion
EXPLANATION_CLIPS = REPO_ROOT / "web" / "src" / "explain" / "clips.json"
GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_videos.py"
# The slides' rendered videos (3D scenes, OpenGL): not clips of the video tool
RENDER_GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_render_scale_video.py"
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
    """The command for each of clips.json's rendered videos: its generator's arguments, into videos/rendered/<name>.mp4."""
    commands: list[list[str]] = []
    for video in cast(list[dict[str, object]], clips.get("rendered", [])):
        output = output_dir / "rendered" / f"{video['name']}.mp4"
        command = [sys.executable, str(RENDER_GENERATOR), *cast(list[str], video["arguments"]), "--output", str(output)]
        commands.append(command + (["--ffmpeg", ffmpeg] if ffmpeg else []))
    return commands


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
    clips = cast(dict[str, object], json.loads(EXPLANATION_CLIPS.read_text(encoding="utf-8")))
    for motion, pairs in with_explanation_clips(required_pairs(definitions), clips).items():
        if motion.startswith("ui"):
            parser.error(f"{TRIALS.name} asks for {motion}: the blind test never uses the rows (ui scroll)")
        bad_pairs = [f"{top}:{bottom}" for top, bottom in pairs if "naive" in top and "naive" in bottom]
        if bad_pairs:
            parser.error(f"{TRIALS.name} compares two bad timers ({', '.join(bad_pairs)}): the blind test never does")
        print(f"{motion}: {len(pairs)} clips", flush=True)
        result = subprocess.run(generator_command(motion, pairs, clip_arguments, args.output_dir, args.ffmpeg), check=False)
        if result.returncode != 0:
            return result.returncode
    for command in rendered_commands(clips, args.output_dir, args.ffmpeg):
        print(f"rendered: {Path(command[command.index('--output') + 1]).name}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
