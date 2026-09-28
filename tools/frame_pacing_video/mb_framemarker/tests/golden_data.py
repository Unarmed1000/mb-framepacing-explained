# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Reads the golden data the C++ library writes with marker-render --golden (test-data/markers): the image manifest, the module
digest and the PGM images. The folder is found above this file, or given by the MB_FRAMEMARKER_TEST_DATA environment variable.
"""

import csv
import os
import unittest
from dataclasses import dataclass
from pathlib import Path

from .. import MarkerKind, Options, Payload, Point, SequenceId, StartMetadata

ENVIRONMENT_VARIABLE = "MB_FRAMEMARKER_TEST_DATA"


@dataclass(frozen=True)
class GoldenMarker:
    file: str
    payload: Payload
    start: StartMetadata
    options: Options
    origin: Point
    width: int
    height: int


@dataclass(frozen=True)
class ModuleDigestRow:
    line: int
    payload: Payload
    start: StartMetadata
    size: int
    modules_hex: str


def marker_directory() -> Path | None:
    """test-data/markers, from the environment variable or the first folder above this file that has it; None when not found."""
    configured = os.environ.get(ENVIRONMENT_VARIABLE)
    if configured:
        return Path(configured)
    for folder in Path(__file__).resolve().parents:
        candidate = folder / "test-data" / "markers"
        if (candidate / "manifest.csv").is_file():
            return candidate
    return None


def require_marker_directory(test: unittest.TestCase) -> Path:
    """The golden data, or skip the test: a copy of the library outside mb-framepacing has no test-data folder."""
    directory = marker_directory()
    if directory is None:
        test.skipTest(f"test-data/markers not found above the tests, and {ENVIRONMENT_VARIABLE} is not set")
    return directory


def _start(row: dict[str, str]) -> StartMetadata:
    """The start metadata; sequenceIdHex is 32 hex digits for a start marker and empty for the other kinds."""
    sequence_id = row["sequenceIdHex"]
    return StartMetadata(int(row["startUtcTicks"]), SequenceId(bytes.fromhex(sequence_id)) if sequence_id else SequenceId())


def _payload(row: dict[str, str]) -> Payload:
    return Payload(
        int(row["frameIndex"]),
        int(row["animationTicks"]),
        int(row["runId"]),
        MarkerKind(int(row["kind"])),
        int(row["intendedDisplayTicks"]),
        int(row["targetFrameTicks"]),
        int(row["cpuStartTicks"]),
        int(row["cpuBusyTicks"]),
    )


def markers(directory: Path) -> list[GoldenMarker]:
    with (directory / "manifest.csv").open(newline="", encoding="ascii") as file:
        rows = list(csv.DictReader(file))
    return [
        GoldenMarker(
            row["file"],
            _payload(row),
            _start(row),
            Options(int(row["moduleSizePx"]), int(row["quietZoneModules"])),
            Point(int(row["originX"]), int(row["originY"])),
            int(row["width"]),
            int(row["height"]),
        )
        for row in rows
    ]


def module_digest(directory: Path) -> list[ModuleDigestRow]:
    with (directory / "modules.csv").open(newline="", encoding="ascii") as file:
        rows = list(csv.DictReader(file))
    return [
        ModuleDigestRow(
            line,
            _payload(row),
            _start(row),
            int(row["size"]),
            row["modulesHex"],
        )
        for line, row in enumerate(rows, start=2)
    ]


def read_pgm(path: Path) -> tuple[bytes, int, int]:
    """Read a binary PGM (P5, 8 bit): the pixel bytes, the width and the height."""
    data = path.read_bytes()
    tokens: list[bytes] = []
    position = 0
    while len(tokens) < 4:
        while data[position : position + 1].isspace():
            position += 1
        start = position
        while not data[position : position + 1].isspace():
            position += 1
        tokens.append(data[start:position])
    if tokens[0] != b"P5" or tokens[3] != b"255":
        raise ValueError(f"{path} is not an 8 bit binary PGM")
    width, height = int(tokens[1]), int(tokens[2])
    position += 1  # the single whitespace after the maximum value
    return data[position : position + (width * height)], width, height
