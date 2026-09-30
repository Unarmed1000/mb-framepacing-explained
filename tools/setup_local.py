#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""The rest of the setup, after uv made .venv: setup.cmd (Windows) or ./setup.sh (Linux, macOS) run this script with uv run, which
first creates or updates .venv (the Python of .python-version, pyproject.toml's dependencies and dev group, as uv.lock pins them).

1. Fetches the mb-framepacing submodule (external/mb-framepacing: the frame marker library) when the clone did not (git clone
   without --recurse-submodules).
2. Creates local.toml (the machine-local settings, git-ignored) from local.example.toml when it is missing; with --ffmpeg it stores
   where FFmpeg is. Then it shows which FFmpeg the tools will use.

Safe to run again at any time. Uses only the standard library.
  uv run tools/setup_local.py [--ffmpeg <ffmpeg executable or its folder>]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG = REPO_ROOT / "local.toml"
LOCAL_EXAMPLE = REPO_ROOT / "local.example.toml"
GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_videos.py"
# The mb-framepacing submodule, at the commit this repository pins; the tools use its marker library
SUBMODULE = REPO_ROOT / "external" / "mb-framepacing"

# The [ffmpeg] path line of local.toml, also when it is still commented out as in local.example.toml
FFMPEG_PATH_LINE = re.compile(r"^#?[ \t]*path[ \t]*=.*$", re.MULTILINE)


def run(command: list[str]) -> None:
    print("> " + " ".join(command), flush=True)
    _ = subprocess.run(command, check=True, cwd=REPO_ROOT)


def write_ffmpeg_path(location: str) -> None:
    """Store the FFmpeg location in local.toml, keeping the rest of the file."""
    path = Path(location).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"--ffmpeg: '{path}' does not exist")
    if "'" in str(path):
        raise SystemExit(f"--ffmpeg: '{path}' contains a single quote; edit {LOCAL_CONFIG.name} by hand instead")
    line = f"path = '{path}'"
    text = LOCAL_CONFIG.read_text(encoding="utf-8") if LOCAL_CONFIG.is_file() else LOCAL_EXAMPLE.read_text(encoding="utf-8")
    if FFMPEG_PATH_LINE.search(text):
        text = FFMPEG_PATH_LINE.sub(lambda _: line, text, count=1)
    else:
        text = text.rstrip("\n") + f"\n\n[ffmpeg]\n{line}\n"
    _ = LOCAL_CONFIG.write_text(text, encoding="utf-8")
    print(f"Stored the FFmpeg location in {LOCAL_CONFIG}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch the mb-framepacing submodule and create or update local.toml (after uv made .venv).")
    _ = parser.add_argument("--ffmpeg", metavar="PATH", help="store the FFmpeg executable (or the folder that holds it) in local.toml")
    ffmpeg: str | None = parser.parse_args().ffmpeg  # pyright: ignore[reportAny]

    if not (SUBMODULE / "sdk" / "marker" / "python" / "mb_framemarker").is_dir():
        run(["git", "-C", str(REPO_ROOT), "submodule", "update", "--init", SUBMODULE.relative_to(REPO_ROOT).as_posix()])

    if ffmpeg is not None:
        write_ffmpeg_path(ffmpeg)
    elif not LOCAL_CONFIG.is_file():
        _ = LOCAL_CONFIG.write_text(LOCAL_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Created {LOCAL_CONFIG} from {LOCAL_EXAMPLE.name}", flush=True)

    print("\nFFmpeg check:", flush=True)
    ffmpeg_found = subprocess.run([sys.executable, str(GENERATOR), "--check-ffmpeg"], check=False, cwd=REPO_ROOT).returncode == 0
    if not ffmpeg_found:
        print(f"Point to FFmpeg with: {'setup.cmd' if sys.platform == 'win32' else './setup.sh'} --ffmpeg <path> (or edit {LOCAL_CONFIG.name})")

    print(
        "\nSetup complete. Run the tools with uv run, for example:\n"
        + "  uv run python -m unittest discover -s tools/frame_pacing_video -v\n"
        + "  uv run tools/frame_pacing_video/generate_videos.py --help"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
