#!/bin/sh
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Create or update the .venv and local.toml (see tools/setup_venv.py). Arguments are passed on, for example:
#   ./setup.sh --ffmpeg /opt/ffmpeg/bin
set -e
cd "$(dirname "$0")"
for candidate in python3.14 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        exec "$candidate" tools/setup_venv.py "$@"
    fi
done
echo "Python 3.14 was not found. Install it, then run ./setup.sh again." >&2
exit 1
