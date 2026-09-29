# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: BSD-3-Clause

"""The package's version is the marker libraries' version (marker/VERSION in mb-framepacing), like the C++ and C# libraries'."""

import unittest
from pathlib import Path

from .. import __version__


class VersionTests(unittest.TestCase):
    def test_the_version_is_the_marker_libraries(self) -> None:
        version = next((folder / "marker" / "VERSION" for folder in Path(__file__).resolve().parents if (folder / "marker" / "VERSION").is_file()), None)
        if version is None:
            self.skipTest("marker/VERSION not found above the tests: a copy of the library outside mb-framepacing")
        self.assertEqual(__version__, version.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    _ = unittest.main()
