# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Sizes, placement, symbol versions, the packed module matrix, the quad walk and the bitmap, as the C# library's GeometryTests."""

import unittest

from .. import (
    MAX_ENCODED_PAYLOAD_BYTE_COUNT,
    MAX_QUAD_COUNT,
    MAX_QUIET_ZONE_MODULES,
    QR_CAPACITY_BYTES,
    QR_MODULE_COUNT,
    QR_VERSION,
    SYNC_QR_MODULE_COUNT,
    SYNC_QR_VERSION,
    MarkerKind,
    ModuleMatrix,
    Options,
    Payload,
    PixelFormat,
    Point,
    Quad,
    SequenceId,
    StartMetadata,
    Vertex,
    generate_modules,
    marker_size_px,
    minimum_module_size_px,
    modules_to_bitmap,
    modules_to_quads,
    packed_module_byte_count,
    qr_module_count_for,
    recommend_module_size_px,
    recommended_origin,
)
from . import software_raster
from .markers import generate_indexed, generate_quads, generate_start_quads, generate_triangles, to_indexed, to_triangles


class GeometryTests(unittest.TestCase):
    def test_buffer_sizes_match_the_cpp_library(self) -> None:
        self.assertEqual(QR_VERSION, 6)
        self.assertEqual(QR_MODULE_COUNT, 41)
        self.assertEqual(QR_CAPACITY_BYTES, 106)
        self.assertEqual(SYNC_QR_VERSION, 2)
        self.assertEqual(SYNC_QR_MODULE_COUNT, 25)
        self.assertEqual(MAX_QUAD_COUNT, 862)
        self.assertEqual(MAX_ENCODED_PAYLOAD_BYTE_COUNT, 72)
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
        self.assertEqual(generate_modules(start, StartMetadata(-1, SequenceId(bytes([0xFF]) * 16))).size, QR_MODULE_COUNT)
        with self.assertRaises(ValueError):
            _ = generate_modules(start, StartMetadata(1 << 63, SequenceId()))

    def test_sync_markers_are_version_2(self) -> None:
        self.assertEqual(generate_modules(Payload(1, 2, 3, MarkerKind.SYNC, 4, 5)).size, SYNC_QR_MODULE_COUNT)
        self.assertEqual(generate_modules(Payload(0xFFFF_FFFF_FFFF_FFFF, 0, 0, MarkerKind.SYNC)).size, 25)
        # The background quad follows the symbol size, in every output
        payload, options, origin = Payload(7, 0, 0, MarkerKind.SYNC), Options(3, 4), Point(10, 20)
        quads = generate_quads(payload, options, origin)
        self.assertEqual(quads[0], Quad(10, 20, 10 + 99, 20 + 99, False))
        self.assertTrue(all(quad.right <= 10 + 99 - 12 and quad.bottom <= 20 + 99 - 12 for quad in quads[1:]))
        self.assertEqual(generate_triangles(payload, options, origin), to_triangles(quads))
        self.assertEqual(generate_indexed(payload, options, origin, 5), to_indexed(quads, 5))
        # The other fields are not encoded: the same symbol whatever they hold
        self.assertEqual(generate_quads(Payload(7, 123, 4, MarkerKind.SYNC, 5, 6), options, origin), quads)

    def test_every_main_marker_kind_has_the_same_size(self) -> None:
        options, origin = Options(), Point(32, 32)
        expected = Quad(32, 32, 32 + 294, 32 + 294, False)
        start = Payload(1, 2, 3, MarkerKind.SEQUENCE_START)
        self.assertEqual(generate_quads(Payload(1, 2, 3), options, origin)[0], expected)
        self.assertEqual(generate_quads(Payload(1, 2, 3, MarkerKind.SEQUENCE_END), options, origin)[0], expected)
        self.assertEqual(generate_start_quads(start, StartMetadata(1, SequenceId.from_text("x" * 16)), options, origin)[0], expected)

    def test_quads_are_pixel_aligned_background_first(self) -> None:
        quads = generate_quads(Payload(5, 6, 7), Options(3, 4), Point(10, 20))
        self.assertTrue(2 <= len(quads) <= MAX_QUAD_COUNT)
        self.assertEqual(quads[0], Quad(10, 20, 10 + 147, 20 + 147, False))
        for quad in quads[1:]:
            self.assertTrue(quad.dark)
            self.assertEqual(quad.height, 3)
            self.assertEqual((quad.left - 22) % 3, 0, "left edges on module boundaries")
            self.assertEqual((quad.top - 32) % 3, 0, "top edges on module boundaries")

    def test_triangles_and_indexed_follow_the_quads_in_the_documented_order(self) -> None:
        payload, options, origin = Payload(42, 1_234_567, 3), Options(2, 4), Point(7, 9)
        quads = generate_quads(payload, options, origin)
        self.assertEqual(generate_triangles(payload, options, origin), to_triangles(quads))
        self.assertEqual(generate_indexed(payload, options, origin, 50), to_indexed(quads, 50))

    def test_vertex_order_matches_the_cpp_library(self) -> None:
        # The background quad comes first: its vertices in the documented order
        options = Options(2, 4)
        size = marker_size_px(options)
        triangles = generate_triangles(Payload(1, 2, 3), options, Point(10, 20))
        light = [
            Vertex(10, 20, 255),
            Vertex(10 + size, 20, 255),
            Vertex(10, 20 + size, 255),
            Vertex(10, 20 + size, 255),
            Vertex(10 + size, 20, 255),
            Vertex(10 + size, 20 + size, 255),
        ]
        self.assertEqual(triangles[:6], light)
        vertices, indices = generate_indexed(Payload(1, 2, 3), options, Point(10, 20), 100)
        self.assertEqual(vertices[:4], [Vertex(10, 20, 255), Vertex(10 + size, 20, 255), Vertex(10 + size, 20 + size, 255), Vertex(10, 20 + size, 255)])
        self.assertEqual(indices[:12], [100, 101, 103, 103, 101, 102, 104, 105, 107, 107, 105, 106])

    def test_invalid_options_raise(self) -> None:
        payload = Payload(1, 2, 3)
        for options in (Options(0), Options(6, -1), Options(6, MAX_QUIET_ZONE_MODULES + 1), Options(1025)):
            with self.subTest(options), self.assertRaises(ValueError):
                _ = generate_quads(payload, options, Point(0, 0))

    def test_markers_fit_the_quad_count(self) -> None:
        for frame in range(0, 500, 7):
            payload = Payload(frame * 7919, frame * 166_667, 9, MarkerKind(frame % 4), frame * 166_700, 166_667)
            self.assertLessEqual(len(generate_quads(payload, Options(), Point(0, 0))), MAX_QUAD_COUNT)


class ModuleMatrixTests(unittest.TestCase):
    def test_bits_are_packed_row_major_most_significant_bit_first(self) -> None:
        for kind in (MarkerKind.FRAME, MarkerKind.SYNC):
            matrix = generate_modules(Payload(12345, 678, 9, kind))
            self.assertEqual(len(matrix.bits), packed_module_byte_count(matrix.size))
            for y in range(matrix.size):
                for x in range(matrix.size):
                    index = (y * matrix.size) + x
                    self.assertEqual(matrix.is_dark(x, y), (matrix.bits[index // 8] >> (7 - (index % 8))) & 1 == 1)
        self.assertEqual((packed_module_byte_count(41), packed_module_byte_count(25)), (211, 79))

    def test_takes_qr_sizes_and_ignores_the_padding(self) -> None:
        matrix = generate_modules(Payload(1, 2, 3, MarkerKind.SYNC))
        padded = bytearray(matrix.bits)
        padded[-1] |= 0x7F  # 625 modules: the last byte uses 1 bit
        self.assertEqual(ModuleMatrix(25, bytes(padded) + b"extra"), matrix)
        for size, bits in ((24, padded), (45, padded), (25, padded[:78])):
            with self.subTest(size), self.assertRaises(ValueError):
                _ = ModuleMatrix(size, bytes(bits))


class BitmapTests(unittest.TestCase):
    def test_equals_the_rasterized_quads_in_every_pixel_format(self) -> None:
        width, height = 173, 131
        cases = [
            (Payload(1, 2, 3), Options(3, 4), Point(5, 7)),
            (Payload(99, -5, 1, MarkerKind.SEQUENCE_END), Options(1, 0), Point(0, 0)),
            (Payload(7, 0, 0, MarkerKind.SYNC), Options(2, 4), Point(3, 1)),
            (Payload(0xFFFF_FFFF_FFFF_FFFF, 1, 2, MarkerKind.FRAME, 3, 4, 5, 6), Options(2, 1), Point(-9, -4)),
        ]
        for payload, options, origin in cases:
            matrix = generate_modules(payload)
            expected = software_raster.quads(modules_to_quads(matrix, options, origin), width, height)
            for pixel_format in PixelFormat:
                with self.subTest(payload=payload, pixel_format=pixel_format):
                    size = pixel_format.bytes_per_pixel
                    stride = (width * size) + 5  # padded rows
                    pixels = bytearray([128]) * (stride * height)
                    modules_to_bitmap(matrix, options, origin, pixels, width, height, pixel_format, stride)
                    for y in range(height):
                        row = pixels[y * stride : (y + 1) * stride]
                        wanted = bytearray()
                        for luma in expected[y * width : (y + 1) * width]:
                            wanted += bytes([luma] * min(size, 3)) + (bytes([255 if luma != 128 else 128]) if size == 4 else b"")
                        self.assertEqual(bytes(row[: width * size]), bytes(wanted), f"row {y}")
                        self.assertEqual(bytes(row[width * size :]), bytes([128] * 5), "the row padding is never written")

    def test_a_module_resolution_image_scaled_up_equals_the_full_size_one(self) -> None:
        matrix = generate_modules(Payload(31, 41, 59))
        small, large, module = Options(1, 4), Options(3, 4), 3
        small_size, large_size = marker_size_px(small), marker_size_px(large)
        modules = bytearray(small_size * small_size)
        pixels = bytearray(large_size * large_size)
        modules_to_bitmap(matrix, small, Point(0, 0), modules, small_size, small_size)
        modules_to_bitmap(matrix, large, Point(0, 0), pixels, large_size, large_size)
        for y in range(large_size):
            for x in range(large_size):
                self.assertEqual(pixels[(y * large_size) + x], modules[((y // module) * small_size) + (x // module)])

    def test_rejects_invalid_arguments_without_writing(self) -> None:
        matrix = generate_modules(Payload(1, 2, 3))
        pixels = bytearray([128]) * (64 * 64 * 4)
        with self.assertRaises(ValueError):
            modules_to_bitmap(matrix, Options(0), Point(0, 0), pixels, 64, 64)
        with self.assertRaises(ValueError):
            modules_to_bitmap(matrix, Options(1, 4), Point(0, 0), pixels, 64, 64, PixelFormat.RGB24, (64 * 3) - 1)
        with self.assertRaises(ValueError):
            modules_to_bitmap(matrix, Options(1, 4), Point(0, 0), memoryview(pixels)[:-1], 64, 64, PixelFormat.RGBA32)
        self.assertTrue(all(value == 128 for value in pixels))
        modules_to_bitmap(matrix, Options(1, 4), Point(500, 500), pixels, 64, 64)
        self.assertTrue(all(value == 128 for value in pixels), "outside the buffer: nothing to draw")


if __name__ == "__main__":
    _ = unittest.main()
