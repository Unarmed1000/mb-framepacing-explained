# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""The Python library must draw exactly what the C++ library draws: the same module matrix for 512 pseudo random payloads
(test-data/markers/modules.csv, 128 per marker kind) and byte identical golden images from quads, triangle lists and indexed
triangle lists, for every kind including the sync marker.
"""

import unittest
from pathlib import Path

from .. import (
    MarkerKind,
    ModuleMatrix,
    generate_indexed,
    generate_modules,
    generate_quads,
    generate_start_indexed,
    generate_start_quads,
    generate_start_triangles,
    generate_triangles,
    qr_module_count_for,
)
from . import golden_data, software_raster


def pack(matrix: ModuleMatrix) -> str:
    """The digest format: row major, one bit per module (1 = dark), most significant bit first, lower case hex."""
    bits = "".join("1" if dark else "0" for row in matrix.rows for dark in row)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8)).hex()


class CrossLanguageTests(unittest.TestCase):
    def test_module_matrices_match_the_cpp_library(self) -> None:
        rows = golden_data.module_digest(golden_data.require_marker_directory(self))
        self.assertEqual(len(rows), 512)
        mismatches: list[str] = []
        for row in rows:
            matrix = generate_modules(row.payload, row.start)
            if matrix.size != row.size or pack(matrix) != row.modules_hex:
                mismatches.append(f"line {row.line}: {row.payload} size {matrix.size} (expected {row.size})")
        self.assertEqual(mismatches, [], "\n".join(mismatches[:10]))
        # Every marker kind is pinned to its version: 6 for the main markers, 2 for the sync marker
        for kind in MarkerKind:
            with self.subTest(kind):
                self.assertEqual({row.size for row in rows if row.payload.kind == kind}, {qr_module_count_for(kind)})

    def test_golden_images_cover_every_marker_kind(self) -> None:
        goldens = golden_data.markers(golden_data.require_marker_directory(self))
        self.assertEqual({golden.payload.kind for golden in goldens}, set(MarkerKind))

    def test_golden_images_from_quads(self) -> None:
        directory = golden_data.require_marker_directory(self)
        for golden in golden_data.markers(directory):
            with self.subTest(golden.file):
                start = golden.payload.kind == MarkerKind.SEQUENCE_START
                quads = (
                    generate_start_quads(golden.payload, golden.start, golden.options, golden.origin)
                    if start
                    else generate_quads(golden.payload, golden.options, golden.origin)
                )
                self.assert_matches_golden(directory, golden, software_raster.quads(quads, golden.width, golden.height))

    def test_golden_images_from_triangles(self) -> None:
        directory = golden_data.require_marker_directory(self)
        for golden in golden_data.markers(directory):
            with self.subTest(golden.file):
                start = golden.payload.kind == MarkerKind.SEQUENCE_START
                vertices = (
                    generate_start_triangles(golden.payload, golden.start, golden.options, golden.origin)
                    if start
                    else generate_triangles(golden.payload, golden.options, golden.origin)
                )
                self.assert_matches_golden(directory, golden, software_raster.triangles(vertices, golden.width, golden.height))

    def test_golden_images_from_indexed_triangles(self) -> None:
        base_vertex = 100
        directory = golden_data.require_marker_directory(self)
        for golden in golden_data.markers(directory):
            with self.subTest(golden.file):
                start = golden.payload.kind == MarkerKind.SEQUENCE_START
                vertices, indices = (
                    generate_start_indexed(golden.payload, golden.start, golden.options, golden.origin, base_vertex)
                    if start
                    else generate_indexed(golden.payload, golden.options, golden.origin, base_vertex)
                )
                expanded = software_raster.expand(vertices, indices, base_vertex)
                self.assert_matches_golden(directory, golden, software_raster.triangles(expanded, golden.width, golden.height))

    def assert_matches_golden(self, directory: Path, golden: golden_data.GoldenMarker, pixels: bytes) -> None:
        expected, width, height = golden_data.read_pgm(directory / golden.file)
        self.assertEqual((width, height), (golden.width, golden.height))
        first = next((i for i, (a, b) in enumerate(zip(pixels, expected, strict=True)) if a != b), -1)
        self.assertEqual(first, -1, f"first difference at ({first % width}, {first // width}) in {golden.file}")


if __name__ == "__main__":
    _ = unittest.main()
