# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Software rasterizers for the tests, matching how marker-render draws the golden images: a 128 grey canvas, pixel-edge vertices,
drawn in order. The triangle rasterizer is the C# tests' (SoftwareRaster.cs), so all three outputs are checked the same way.
"""

from .. import Quad, Vertex, fill_quads

BACKGROUND = 128


def quads(quad_list: list[Quad], width: int, height: int) -> bytes:
    """Fill pixel (x, y) when left <= x < right and top <= y < bottom, through the library's own fill_quads."""
    pixels = bytearray([BACKGROUND]) * (width * height)
    fill_quads(pixels, width, height, quad_list)
    return bytes(pixels)


def triangles(vertices: list[Vertex], width: int, height: int) -> bytes:
    """Sample pixel centres like a GPU: pixel (x, y) is covered when (x + 0.5, y + 0.5) lies inside the triangle or on an edge."""
    pixels = bytearray([BACKGROUND]) * (width * height)
    for i in range(0, len(vertices) - 2, 3):
        v0, v1, v2 = vertices[i], vertices[i + 1], vertices[i + 2]
        min_x = max(0, min(v0.x, v1.x, v2.x))
        max_x = min(width, max(v0.x, v1.x, v2.x))
        min_y = max(0, min(v0.y, v1.y, v2.y))
        max_y = min(height, max(v0.y, v1.y, v2.y))
        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                # Doubled coordinates keep the pixel centres integral
                px, py = (2 * x) + 1, (2 * y) + 1
                e0, e1, e2 = _edge(v0, v1, px, py), _edge(v1, v2, px, py), _edge(v2, v0, px, py)
                if (e0 >= 0 and e1 >= 0 and e2 >= 0) or (e0 <= 0 and e1 <= 0 and e2 <= 0):
                    pixels[(y * width) + x] = v0.luma
    return bytes(pixels)


def expand(vertices: list[Vertex], indices: list[int], base_vertex: int) -> list[Vertex]:
    """Expand an indexed triangle list into a plain one."""
    return [vertices[index - base_vertex] for index in indices]


def _edge(a: Vertex, b: Vertex, px: int, py: int) -> int:
    return (2 * (b.x - a.x) * (py - (2 * a.y))) - (2 * (b.y - a.y) * (px - (2 * a.x)))
