#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Create or update the repository's .venv with one command: setup.cmd (Windows) or ./setup.sh (Linux, macOS) run this script.

1. Checks that this is Python 3.14 or newer.
2. Creates .venv when it is missing (or was made by an older Python, or in another folder before the repository was moved).
3. Upgrades pip in it and installs the dev dependency group of pyproject.toml (Pillow, ruff, basedpyright).
4. Creates local.toml (the machine-local settings, git-ignored) from local.example.toml when it is missing; with --ffmpeg it
   stores where FFmpeg is. Then it shows which FFmpeg the tools will use.

Safe to run again at any time, for example after pyproject.toml changes. Uses only the standard library.
  python tools/setup_venv.py [--ffmpeg <ffmpeg executable or its folder>]
"""

import argparse
import os
import re
import subprocess
import sys
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
LOCAL_CONFIG = REPO_ROOT / "local.toml"
LOCAL_EXAMPLE = REPO_ROOT / "local.example.toml"
GENERATOR = REPO_ROOT / "tools" / "frame_pacing_video" / "generate_videos.py"
MIN_PYTHON = (3, 14)

# The [ffmpeg] path line of local.toml, also when it is still commented out as in local.example.toml
FFMPEG_PATH_LINE = re.compile(r"^#?[ \t]*path[ \t]*=.*$", re.MULTILINE)


def venv_python() -> Path:
    return VENV_DIR / "Scripts" / "python.exe" if sys.platform == "win32" else VENV_DIR / "bin" / "python"


def run(command: list[str]) -> None:
    print("> " + " ".join(command), flush=True)
    _ = subprocess.run(command, check=True, cwd=REPO_ROOT)


def venv_was_made_here() -> bool:
    """False when .venv was created in another folder (the repository was moved or renamed): its Python still runs, but the
    launchers of its tools (pip, ruff, basedpyright) point to the old folder. Its pyvenv.cfg names the folder it was made in."""
    config = VENV_DIR / "pyvenv.cfg"
    lines = config.read_text(encoding="utf-8").splitlines() if config.is_file() else []
    command = next((line.split("=", 1)[1] for line in lines if line.split("=", 1)[0].strip() == "command"), None)
    return command is None or os.path.normcase(str(VENV_DIR)) in os.path.normcase(command)


def venv_is_current() -> bool:
    """True when .venv has a working Python of at least MIN_PYTHON, made in this folder."""
    python = venv_python()
    if not python.is_file() or not venv_was_made_here():
        return False
    check = f"import sys; sys.exit(0 if sys.version_info >= {MIN_PYTHON} else 1)"
    return subprocess.run([str(python), "-c", check], check=False).returncode == 0


def create_venv() -> None:
    if venv_is_current():
        print(f"Using the existing {VENV_DIR}", flush=True)
        return
    print(f"Creating {VENV_DIR}", flush=True)
    venv.EnvBuilder(with_pip=True, clear=VENV_DIR.exists()).create(VENV_DIR)


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
    parser = argparse.ArgumentParser(description="Create or update the .venv and local.toml of this repository.")
    _ = parser.add_argument("--ffmpeg", metavar="PATH", help="store the FFmpeg executable (or the folder that holds it) in local.toml")
    ffmpeg: str | None = parser.parse_args().ffmpeg  # pyright: ignore[reportAny]

    if sys.version_info < MIN_PYTHON:
        print(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is needed, this is {sys.version.split()[0]} ({sys.executable}).\n"
            + "Install it from https://www.python.org/downloads/ (Windows: winget install Python.Python.3.14), then run setup again.",
            file=sys.stderr,
        )
        return 1

    create_venv()
    python = str(venv_python())
    run([python, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "--disable-pip-version-check", "--group", "dev"])

    if ffmpeg is not None:
        write_ffmpeg_path(ffmpeg)
    elif not LOCAL_CONFIG.is_file():
        _ = LOCAL_CONFIG.write_text(LOCAL_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Created {LOCAL_CONFIG} from {LOCAL_EXAMPLE.name}", flush=True)

    print("\nFFmpeg check:", flush=True)
    ffmpeg_found = subprocess.run([python, str(GENERATOR), "--check-ffmpeg"], check=False, cwd=REPO_ROOT).returncode == 0
    if not ffmpeg_found:
        print(f"Point to FFmpeg with: {'setup.cmd' if sys.platform == 'win32' else './setup.sh'} --ffmpeg <path> (or edit {LOCAL_CONFIG.name})")

    activate = r".venv\Scripts\activate" if sys.platform == "win32" else "source .venv/bin/activate"
    print(
        "\nSetup complete. Next steps:\n"
        + f"  {activate}\n"
        + "  python -m unittest discover -s tools/frame_pacing_video -v\n"
        + "  python tools/frame_pacing_video/generate_videos.py --help"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
