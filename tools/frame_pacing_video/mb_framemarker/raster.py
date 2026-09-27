# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Drawing the marker into a pixel buffer. The C# and C++ libraries leave drawing to the GPU; a Python caller usually has a buffer
(a bytearray of rgb24 or grey pixels, PIL's Image.tobytes, a numpy array's memory), so this fills the quads into it the way
marker-render draws the golden images.
"""

from .structures import Quad


def fill_quads(buffer: bytearray | memoryview, width: int, height: int, quads: list[Quad], channels: int = 1, stride: int | None = None) -> None:
    """Fill every quad, in order, into `buffer`: `width` x `height` pixels of `channels` bytes each (1 for grey, 3 for rgb24), rows
    `stride` bytes apart (default width x channels). A quad covers left <= x < right and top <= y < bottom, clipped to the buffer,
    in pure black (0) or white (255) on every channel."""
    if channels < 1 or width < 0 or height < 0:
        raise ValueError(f"invalid buffer: {width} x {height} pixels of {channels} channels")
    row_bytes = width * channels
    stride = row_bytes if stride is None else stride
    needed = 0 if height == 0 else (stride * (height - 1)) + row_bytes
    if stride < row_bytes or len(buffer) < needed:
        raise ValueError(f"a buffer of {len(buffer)} bytes is too small for {width} x {height} pixels of {channels} channels, stride {stride}")
    for quad in quads:
        left, right = max(quad.left, 0), min(quad.right, width)
        top, bottom = max(quad.top, 0), min(quad.bottom, height)
        if left >= right or top >= bottom:
            continue
        run = bytes([0 if quad.dark else 255]) * ((right - left) * channels)
        for y in range(top, bottom):
            start = (y * stride) + (left * channels)
            buffer[start : start + len(run)] = run
