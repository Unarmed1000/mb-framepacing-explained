# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Sizes, placement, symbol versions and the quad walk, as the C# library's GeometryTests; and fill_quads."""

import unittest

from .. import (
    MAX_ENCODED_PAYLOAD_BYTE_COUNT,
    MAX_QUAD_COUNT,
    MAX_QUIET_ZONE_MODULES,
    MAX_START_NAME_BYTES,
    QR_CAPACITY_BYTES,
    QR_MODULE_COUNT,
    QR_VERSION,
    SYNC_QR_MODULE_COUNT,
    SYNC_QR_VERSION,
    MarkerKind,
    Options,
    Payload,
    Point,
    Quad,
    StartMetadata,
    Vertex,
    fill_quads,
    generate_indexed,
    generate_modules,
    generate_quads,
    generate_start_quads,
    generate_triangles,
    marker_size_px,
    minimum_module_size_px,
    qr_module_count_for,
    quads_to_indexed,
    quads_to_triangles,
    recommend_module_size_px,
    recommended_origin,
)


class GeometryTests(unittest.TestCase):
    def test_buffer_sizes_match_the_cpp_library(self) -> None:
        self.assertEqual(QR_VERSION, 6)
        self.assertEqual(QR_MODULE_COUNT, 41)
        self.assertEqual(QR_CAPACITY_BYTES, 106)
        self.assertEqual(SYNC_QR_VERSION, 2)
        self.assertEqual(SYNC_QR_MODULE_COUNT, 25)
        self.assertEqual(MAX_QUAD_COUNT, 862)
        self.assertEqual(MAX_ENCODED_PAYLOAD_BYTE_COUNT, 105)
        self.assertLessEqual(MAX_ENCODED_PAYLOAD_BYTE_COUNT, QR_CAPACITY_BYTES)

    def test_marker_size(self) -> None:
        self.assertEqual(marker_size_px(Options()), 294)
        self.assertEqual(marker_size_px(Options(3)), 147)
        self.assertEqual(marker_size_px(Options(4)), 196)
        self.assertEqual(marker_size_px(Options(12)), 588)
        self.assertEqual(marker_size_px(Options(1, 0)), 41)
        for kind in (MarkerKind.FRAME, MarkerKind.SEQUENCE_START, MarkerKind.SEQUENCE_END):
            self.assertEqual(marker_size_px(Options(), kind), 294)
            self.assertEqual(qr_module_count_for(kind), QR_MODULE_COUNT)

    def test_sync_marker_size(self) -> None:
        self.assertEqual(qr_module_count_for(MarkerKind.SYNC), SYNC_QR_MODULE_COUNT)
        self.assertEqual(marker_size_px(Options(), MarkerKind.SYNC), 198)
        self.assertEqual(marker_size_px(Options(3), MarkerKind.SYNC), 99)
        self.assertEqual(marker_size_px(Options(1, 0), MarkerKind.SYNC), 25)

    def test_module_size_recommendations_match_the_documentation(self) -> None:
        self.assertEqual(minimum_module_size_px(1080, 1080), 2)
        self.assertEqual(recommend_module_size_px(1080, 1080), 3)
        self.assertEqual(recommend_module_size_px(1080, 1080, mjpeg=True), 4)
        self.assertEqual(minimum_module_size_px(1440, 1080), 3)
        self.assertEqual(recommend_module_size_px(1440, 1080), 4)
        self.assertEqual(minimum_module_size_px(1080, 540), 4)
        self.assertEqual(recommend_module_size_px(1080, 540), 6)
        self.assertEqual(recommend_module_size_px(2160, 1080), 6)
        self.assertEqual(recommend_module_size_px(1080, 540, mjpeg=True), 8)
        self.assertEqual(minimum_module_size_px(1080, 360), 6)
        self.assertEqual(recommend_module_size_px(1080, 360), 9)
        self.assertEqual(minimum_module_size_px(2160, 540), 8)
        self.assertEqual(recommend_module_size_px(2160, 540), 12)
        self.assertEqual(recommend_module_size_px(540, 1080), 3)
        self.assertEqual(recommend_module_size_px(0, 1080), 3)

    def test_recommended_origins(self) -> None:
        options = Options()
        # The main marker top-left, the sync marker bottom-left
        self.assertEqual(recommended_origin(MarkerKind.FRAME, 1920, 1080, options), Point(32, 32))
        self.assertEqual(recommended_origin(MarkerKind.SEQUENCE_START, 1920, 1080, options), Point(32, 32))
        self.assertEqual(recommended_origin(MarkerKind.SEQUENCE_END, 1920, 1080, options), Point(32, 32))
        self.assertEqual(recommended_origin(MarkerKind.SYNC, 1920, 1080, options), Point(32, 1080 - 32 - 198))
        # Aligned to a 3:1 downscale ratio
        self.assertEqual(recommended_origin(MarkerKind.FRAME, 1920, 1080, options, 3), Point(33, 33))
        self.assertEqual(recommended_origin(MarkerKind.SYNC, 1920, 1080, options, 3), Point(33, 849))
        self.assertEqual(recommended_origin(MarkerKind.FRAME, 1920, 1080, options, 4), Point(32, 32))
        # A frame lower than the marker: C# and C++ truncate toward zero, Python's // would floor
        self.assertEqual(recommended_origin(MarkerKind.SYNC, 100, 100, options), Point(32, -130))
        self.assertEqual(recommended_origin(MarkerKind.SYNC, 100, 100, options, 3), Point(33, -129))

    def test_every_main_marker_kind_is_version_6(self) -> None:
        for kind in (MarkerKind.FRAME, MarkerKind.SEQUENCE_START, MarkerKind.SEQUENCE_END):
            with self.subTest(kind):
                self.assertEqual(generate_modules(Payload(1, 2, 3, kind, 4, 5)).size, 41)
        start = Payload(1, 2, 3, MarkerKind.SEQUENCE_START)
        self.assertEqual(generate_modules(start, StartMetadata(0, "x" * MAX_START_NAME_BYTES)).size, QR_MODULE_COUNT)
        with self.assertRaises(ValueError):
            _ = generate_modules(start, StartMetadata(0, "x" * (MAX_START_NAME_BYTES + 1)))

    def test_sync_markers_are_version_2(self) -> None:
        self.assertEqual(generate_modules(Payload(1, 2, 3, MarkerKind.SYNC, 4, 5)).size, SYNC_QR_MODULE_COUNT)
        self.assertEqual(generate_modules(Payload(0xFFFF_FFFF_FFFF_FFFF, 0, 0, MarkerKind.SYNC)).size, 25)
        # The background quad follows the symbol size, in every output
        payload, options, origin = Payload(7, 0, 0, MarkerKind.SYNC), Options(3, 4), Point(10, 20)
        quads = generate_quads(payload, options, origin)
        self.assertEqual(quads[0], Quad(10, 20, 10 + 99, 20 + 99, False))
        self.assertTrue(all(quad.right <= 10 + 99 - 12 and quad.bottom <= 20 + 99 - 12 for quad in quads[1:]))
        self.assertEqual(generate_triangles(payload, options, origin), quads_to_triangles(quads))
        self.assertEqual(generate_indexed(payload, options, origin, 5), quads_to_indexed(quads, 5))
        # The other fields are not encoded: the same symbol whatever they hold
        self.assertEqual(generate_quads(Payload(7, 123, 4, MarkerKind.SYNC, 5, 6), options, origin), quads)

    def test_every_main_marker_kind_has_the_same_size(self) -> None:
        options, origin = Options(), Point(32, 32)
        expected = Quad(32, 32, 32 + 294, 32 + 294, False)
        start = Payload(1, 2, 3, MarkerKind.SEQUENCE_START)
        self.assertEqual(generate_quads(Payload(1, 2, 3), options, origin)[0], expected)
        self.assertEqual(generate_quads(Payload(1, 2, 3, MarkerKind.SEQUENCE_END), options, origin)[0], expected)
        self.assertEqual(generate_start_quads(start, StartMetadata(0, "x" * MAX_START_NAME_BYTES), options, origin)[0], expected)

    def test_quads_are_pixel_aligned_background_first(self) -> None:
        quads = generate_quads(Payload(5, 6, 7), Options(3, 4), Point(10, 20))
        self.assertTrue(2 <= len(quads) <= MAX_QUAD_COUNT)
        self.assertEqual(quads[0], Quad(10, 20, 10 + 147, 20 + 147, False))
        for quad in quads[1:]:
            self.assertTrue(quad.dark)
            self.assertEqual(quad.height, 3)
            self.assertEqual((quad.left - 22) % 3, 0, "left edges on module boundaries")
            self.assertEqual((quad.top - 32) % 3, 0, "top edges on module boundaries")

    def test_triangles_and_indexed_equal_the_converted_quads(self) -> None:
        payload, options, origin = Payload(42, 1_234_567, 3), Options(2, 4), Point(7, 9)
        quads = generate_quads(payload, options, origin)
        self.assertEqual(generate_triangles(payload, options, origin), quads_to_triangles(quads))
        self.assertEqual(generate_indexed(payload, options, origin, 50), quads_to_indexed(quads, 50))

    def test_vertex_order_matches_the_cpp_library(self) -> None:
        quads = [Quad(0, 0, 10, 10, False), Quad(2, 3, 4, 5, True)]
        triangles = quads_to_triangles(quads)
        self.assertEqual(len(triangles), 12)
        light = [Vertex(0, 0, 255), Vertex(10, 0, 255), Vertex(0, 10, 255), Vertex(0, 10, 255), Vertex(10, 0, 255), Vertex(10, 10, 255)]
        self.assertEqual(triangles[:6], light)
        self.assertEqual(triangles[6], Vertex(2, 3, 0))
        self.assertEqual(triangles[11], Vertex(4, 5, 0))

        vertices, indices = quads_to_indexed(quads, 100)
        self.assertEqual(len(vertices), 8)
        self.assertEqual(vertices[4:], [Vertex(2, 3, 0), Vertex(4, 3, 0), Vertex(4, 5, 0), Vertex(2, 5, 0)])
        self.assertEqual(indices, [100, 101, 103, 103, 101, 102, 104, 105, 107, 107, 105, 106])

    def test_invalid_options_raise(self) -> None:
        payload = Payload(1, 2, 3)
        for options in (Options(0), Options(6, -1), Options(6, MAX_QUIET_ZONE_MODULES + 1), Options(1025)):
            with self.subTest(options), self.assertRaises(ValueError):
                _ = generate_quads(payload, options, Point(0, 0))

    def test_markers_fit_the_quad_count(self) -> None:
        for frame in range(0, 500, 7):
            payload = Payload(frame * 7919, frame * 166_667, 9, MarkerKind(frame % 4), frame * 166_700, 166_667)
            self.assertLessEqual(len(generate_quads(payload, Options(), Point(0, 0))), MAX_QUAD_COUNT)


class FillQuadsTests(unittest.TestCase):
    def test_fills_every_channel_in_order_clipped(self) -> None:
        pixels = bytearray([7]) * (4 * 3 * 3)
        fill_quads(pixels, 4, 3, [Quad(-1, -1, 3, 2, False), Quad(1, 1, 9, 9, True)], channels=3)
        rows = [pixels[y * 12 : (y + 1) * 12] for y in range(3)]
        self.assertEqual(rows[0], bytes([255] * 9 + [7] * 3))
        self.assertEqual(rows[1], bytes([255] * 3 + [0] * 9))
        self.assertEqual(rows[2], bytes([7] * 3 + [0] * 9))

    def test_stride_leaves_the_padding(self) -> None:
        pixels = bytearray([7]) * (3 * 2)
        fill_quads(pixels, 2, 2, [Quad(0, 0, 2, 2, True)], stride=3)
        self.assertEqual(pixels, bytearray([0, 0, 7, 0, 0, 7]))

    def test_rejects_a_small_buffer(self) -> None:
        with self.assertRaises(ValueError):
            fill_quads(bytearray(5), 2, 3, [])
        with self.assertRaises(ValueError):
            fill_quads(bytearray(12), 2, 2, [], channels=3, stride=5)


if __name__ == "__main__":
    _ = unittest.main()
