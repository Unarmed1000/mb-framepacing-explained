#!/bin/sh
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Set up the repository: uv creates or updates .venv (Python from .python-version, packages from uv.lock), then
# tools/setup_local.py fetches the mb-framepacing submodule and creates local.toml. Arguments are passed on, for example:
#   ./setup.sh --ffmpeg /opt/ffmpeg/bin
set -e
cd "$(dirname "$0")"
if ! command -v uv >/dev/null 2>&1; then
    echo "uv was not found. Install it (https://docs.astral.sh/uv/: curl -LsSf https://astral.sh/uv/install.sh | sh), then run ./setup.sh again." >&2
    exit 1
fi
exec uv run tools/setup_local.py "$@"
