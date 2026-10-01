# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Puts mb-framepacing's Python SDK (mb_framepacing, its sdk/python; the tools use its marker module, mb_framepacing.marker) on the
import path: it comes from the submodule external/mb-framepacing, pinned to a commit of mb-framepacing (CONTRIBUTING.md says how to
move the pin). Import this module before mb_framepacing; a checkout without the submodule gets an ImportError saying how to fetch it.
"""

import sys
from pathlib import Path

MARKER_LIBRARY = Path(__file__).resolve().parents[2] / "external" / "mb-framepacing" / "sdk" / "python"

if not (MARKER_LIBRARY / "mb_framepacing" / "marker").is_dir():
    raise ImportError(f"mb-framepacing's marker library is missing ({MARKER_LIBRARY}): run git submodule update --init")
if str(MARKER_LIBRARY) not in sys.path:
    sys.path.insert(0, str(MARKER_LIBRARY))
